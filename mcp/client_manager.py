"""MCP client manager for handling multiple MCP server connections."""

import asyncio
import json
import logging
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from contextlib import asynccontextmanager

from utils.config import MCPConfig


@dataclass
class MCPServer:
    """Represents an MCP server process."""
    name: str
    process: subprocess.Popen
    stdin: asyncio.StreamWriter
    stdout: asyncio.StreamReader
    running: bool = True
    last_health_check: Optional[float] = None


class MCPClientManager:
    """Manages multiple MCP server connections."""
    
    def __init__(self, config: MCPConfig):
        self.config = config
        self.servers: Dict[str, MCPServer] = {}
        self.logger = logging.getLogger(__name__)
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        
    async def start_server(self, name: str, command: List[str]) -> bool:
        """Start an MCP server."""
        try:
            self.logger.info(f"Starting MCP server: {name}")
            
            # Prepare environment - pass through important env vars like GITHUB_TOKEN
            import os
            env = os.environ.copy()
            
            # Debug: log environment variables related to GitHub
            self.logger.info(f"Starting {name} with GITHUB_TOKEN: {'GITHUB_TOKEN' in env}")
            if 'GITHUB_TOKEN' in env:
                self.logger.info(f"GITHUB_TOKEN length: {len(env['GITHUB_TOKEN'])}")
            self.logger.info(f"All env vars with 'GITHUB': {[k for k in env.keys() if 'GITHUB' in k.upper()]}")
            
            # Ensure PATH includes GitHub CLI location for potential authentication
            if 'PATH' in env:
                env['PATH'] = f"/opt/homebrew/bin:{env['PATH']}"
            else:
                env['PATH'] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # Pass environment variables to subprocess
            )
            
            server = MCPServer(
                name=name,
                process=process,
                stdin=process.stdin,
                stdout=process.stdout
            )
            
            self.servers[name] = server
            
            # Start response handler
            asyncio.create_task(self._handle_responses(server))
            
            # Initialize connection
            await self._initialize_server(server)
            
            self.logger.info(f"MCP server {name} started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start MCP server {name}: {e}")
            return False
    
    async def stop_server(self, name: str):
        """Stop an MCP server."""
        if name not in self.servers:
            return
            
        server = self.servers[name]
        server.running = False
        
        try:
            if server.process.returncode is None:
                server.process.terminate()
                await asyncio.wait_for(server.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            server.process.kill()
        except Exception as e:
            self.logger.error(f"Error stopping server {name}: {e}")
        
        del self.servers[name]
        self.logger.info(f"MCP server {name} stopped")
    
    async def start_all(self) -> bool:
        """Start all configured MCP servers."""
        success = True
        
        # Start GitHub server
        if not await self.start_server("github", self.config.github_server_command):
            success = False
        
        # Start PyTorch HUD server
        if not await self.start_server("pytorch_hud", self.config.pytorch_hud_server_command):
            success = False
        
        return success
    
    async def stop_all(self):
        """Stop all MCP servers."""
        tasks = []
        for name in list(self.servers.keys()):
            tasks.append(self.stop_server(name))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on an MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not running")
        
        server = self.servers[server_name]
        request_id = self._get_next_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        # Send request
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            request_data = json.dumps(request) + "\n"
            server.stdin.write(request_data.encode())
            await server.stdin.drain()
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"Tool call {tool_name} timed out")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise RuntimeError(f"Tool call failed: {e}")
    
    async def list_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """List available tools from an MCP server."""
        if server_name not in self.servers:
            raise ValueError(f"Server {server_name} not running")
        
        server = self.servers[server_name]
        request_id = self._get_next_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list"
        }
        
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            request_data = json.dumps(request) + "\n"
            server.stdin.write(request_data.encode())
            await server.stdin.drain()
            
            response = await asyncio.wait_for(future, timeout=10.0)
            return response.get("tools", [])
            
        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError("List tools request timed out")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise RuntimeError(f"List tools failed: {e}")
    
    async def health_check(self, server_name: str) -> bool:
        """Check if an MCP server is healthy."""
        try:
            await self.list_tools(server_name)
            return True
        except Exception:
            return False
    
    async def _initialize_server(self, server: MCPServer):
        """Initialize connection with an MCP server."""
        request_id = self._get_next_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "pytorch-issue-agent",
                    "version": "1.0.0"
                }
            }
        }
        
        future = asyncio.Future()
        self._pending_requests[request_id] = future
        
        try:
            request_data = json.dumps(request) + "\n"
            server.stdin.write(request_data.encode())
            await server.stdin.drain()
            
            await asyncio.wait_for(future, timeout=self.config.startup_timeout)
            self.logger.debug(f"Server {server.name} initialized")
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize server {server.name}: {e}")
    
    async def _handle_responses(self, server: MCPServer):
        """Handle responses from an MCP server."""
        try:
            while server.running:
                line = await server.stdout.readline()
                if not line:
                    break
                
                try:
                    response = json.loads(line.decode().strip())
                    request_id = response.get("id")
                    
                    if request_id in self._pending_requests:
                        future = self._pending_requests.pop(request_id)
                        
                        if "error" in response:
                            future.set_exception(RuntimeError(response["error"]["message"]))
                        else:
                            future.set_result(response.get("result", {}))
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"Invalid JSON from server {server.name}: {e}")
                except Exception as e:
                    self.logger.error(f"Error handling response from {server.name}: {e}")
        
        except Exception as e:
            self.logger.error(f"Response handler for {server.name} crashed: {e}")
            server.running = False
    
    def _get_next_request_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id
    
    @asynccontextmanager
    async def managed_servers(self):
        """Context manager for MCP servers."""
        try:
            await self.start_all()
            yield self
        finally:
            await self.stop_all()