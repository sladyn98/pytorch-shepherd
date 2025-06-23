#!/usr/bin/env python3
"""
Simple PyTorch HUD MCP server.
Responds to MCP protocol requests with test failure data.
"""

import asyncio
import json
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


async def handle_request(request_line: str) -> str:
    """Handle incoming JSON-RPC request."""
    try:
        request = json.loads(request_line)
        method = request.get("method", "")
        params = request.get("params", {})
        request_id = request.get("id")
        
        logger.info(f"Received request: {method}")
        
        if method == "initialize":
            # Return server capabilities
            return json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "pytorch-hud",
                        "version": "1.0.0"
                    }
                }
            })
            
        elif method == "tools/list":
            # List available tools
            return json.dumps({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_failing_tests",
                            "description": "Get failing tests for a specific PR number",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "pr_number": {
                                        "type": "integer",
                                        "description": "The pull request number"
                                    }
                                },
                                "required": ["pr_number"]
                            }
                        }
                    ]
                }
            })
            
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            
            if tool_name == "get_failing_tests":
                pr_number = arguments.get("pr_number", 0)
                
                # In a real implementation, this would query the actual PyTorch HUD API
                # For now, return an empty list or mock data based on environment
                failing_tests = []
                
                # If in development/testing mode, you might want to load test data from a file
                import os
                if os.getenv('PYTORCH_HUD_MOCK_MODE'):
                    import json
                    mock_file = os.getenv('PYTORCH_HUD_MOCK_FILE', 'mock_test_failures.json')
                    if os.path.exists(mock_file):
                        with open(mock_file) as f:
                            failing_tests = json.load(f)
                
                result = {
                    "failing_tests": failing_tests,
                    "pr_number": pr_number,
                    "total_failures": len(failing_tests),
                    "status": "failing"
                }
                
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                })
        
        # Return empty result for other methods
        return json.dumps({
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {}
        })
        
    except Exception as e:
        logger.error(f"Error handling request: {e}")
        return json.dumps({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        })


async def main():
    """Main server loop - reads JSON-RPC from stdin and writes to stdout."""
    logger.info("PyTorch HUD MCP server starting...")
    
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
                
            line = line.strip()
            if not line:
                continue
            
            logger.info(f"Received: {line[:100]}...")
            response = await handle_request(line)
            print(response)
            sys.stdout.flush()
            
        except Exception as e:
            logger.error(f"Server error: {e}")
            error_response = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                }
            })
            print(error_response)
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())