#!/usr/bin/env python3
"""
Simple PyTorch HUD MCP server.
Responds to MCP protocol requests with test failure data.
"""

import asyncio
import json
import sys
import logging
import os
import httpx
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


async def get_failing_tests_from_hud(pr_number: int) -> List[Dict[str, Any]]:
    """Query PyTorch HUD API for failing tests."""
    try:
        # Use the actual HUD API endpoints
        hud_api_url = "https://hud.pytorch.org/api/pytorch/pytorch"
        
        async with httpx.AsyncClient() as client:
            # Get commit information for PR
            pr_commits_response = await client.get(
                f"{hud_api_url}/pr/{pr_number}",
                timeout=30.0
            )
            
            if pr_commits_response.status_code != 200:
                logger.warning(f"Failed to get PR commits for #{pr_number}: {pr_commits_response.status_code}")
                return []
            
            pr_commits_data = pr_commits_response.json()
            
            # Get the latest commit SHA
            if not pr_commits_data or "shas" not in pr_commits_data or not pr_commits_data["shas"]:
                logger.warning(f"No commits found for PR #{pr_number}")
                return []
            
            latest_sha = pr_commits_data["shas"][0][0]  # First element is [sha, message]
            logger.info(f"Getting failures for PR #{pr_number}, commit {latest_sha}")
            
            # Get job failures for the commit
            failures_response = await client.get(
                f"{hud_api_url}/commit/{latest_sha}/job_statuses",
                timeout=30.0
            )
            
            if failures_response.status_code != 200:
                logger.warning(f"Failed to get job statuses for commit {latest_sha}: {failures_response.status_code}")
                return []
            
            job_data = failures_response.json()
            
            # Extract failing tests from job data
            failing_tests = []
            seen_tests = set()
            
            for job in job_data:
                if job.get("conclusion") == "failure":
                    job_name = job.get("name", "")
                    
                    # Look for test failures in failure captures
                    if "failureCaptures" in job:
                        for capture in job["failureCaptures"]:
                            if capture and "::" in capture:
                                # Parse test name from pytest format
                                test_parts = capture.split("::", 1)
                                test_file = test_parts[0].replace("/", ".").replace(".py", "")
                                test_name = test_parts[1] if len(test_parts) > 1 else capture
                                
                                test_key = f"{test_file}::{test_name}"
                                if test_key not in seen_tests:
                                    seen_tests.add(test_key)
                                    
                                    # Extract error message from failure lines
                                    error_message = ""
                                    if "failureLines" in job:
                                        for line in job["failureLines"]:
                                            if "FAILED" in line and test_name in line:
                                                error_message = line.split(" - ", 1)[1] if " - " in line else line
                                                break
                                    
                                    test_info = {
                                        "name": test_key,
                                        "test_name": test_name,
                                        "suite": test_file,
                                        "workflow": job.get("workflowName", ""),
                                        "job_name": job_name,
                                        "error_message": error_message or "Test failed",
                                        "failure_message": error_message or "Test failed",
                                        "log_url": job.get("logUrl", ""),
                                        "status": "failed",
                                        "file_path": test_parts[0] if test_parts else "",
                                        "duration": None,
                                        "traceback": None,
                                        "line_number": None
                                    }
                                    failing_tests.append(test_info)
            
            logger.info(f"Found {len(failing_tests)} failing tests for PR #{pr_number}")
            return failing_tests
            
    except Exception as e:
        logger.error(f"Error querying HUD API: {e}")
        return []


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
                
                # Query the actual PyTorch HUD API
                failing_tests = await get_failing_tests_from_hud(pr_number)
                
# No mock mode - always use real API data
                
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