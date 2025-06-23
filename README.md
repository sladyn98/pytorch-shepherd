# 🤖 PyTorch Issue Fixing Agent

An autonomous AI agent that automatically analyzes, fixes, and creates pull requests for PyTorch GitHub issues using Claude AI and Model Context Protocol (MCP) servers.

## ✨ Features

- 🔍 **Intelligent Issue Analysis** - Automatically categorizes and analyzes PyTorch issues
- 🛠️ **Autonomous Code Fixing** - Uses Claude CLI to directly modify code files  
- 🌿 **Git Integration** - Creates branches, commits changes, and pushes to repositories
- 🔄 **Pull Request Creation** - Automatically creates PRs with detailed descriptions
- 📊 **Progress Monitoring** - Tracks fix attempts and maintains state across runs
- 🔐 **Secure Operations** - Integrates with GitHub MCP servers for safe API operations
- ⚡ **Local Repository Support** - Works directly with local PyTorch clones for faster operations

## Architecture

```
pytorch_issue_agent/
├── main.py                 # Entry point
├── agent/
│   ├── controller.py       # Main agent orchestration
│   ├── workflow.py         # State machine implementation
│   └── state_manager.py    # Persistent state handling
├── mcp/
│   ├── client_manager.py   # MCP client lifecycle management
│   ├── github_client.py    # GitHub MCP wrapper
│   └── pytorch_hud_client.py # PyTorch HUD MCP wrapper
├── claude/
│   ├── client.py           # Anthropic API client
│   └── prompts.py          # Prompt templates
└── utils/
    ├── config.py           # Configuration management
    └── logging.py          # Structured logging
```

## Workflow States

1. **FETCHING** - Retrieve issue details from GitHub
2. **ANALYZING** - Analyze issue with Claude to understand the problem
3. **FIXING** - Generate and apply code fixes
4. **CREATING_PR** - Create pull request with fixes
5. **MONITORING** - Monitor CI tests and review comments (every 5 hours)
6. **ADDRESSING_REVIEWS** - Address review feedback and fix failing tests
7. **COMPLETED** - Issue successfully resolved
8. **FAILED** - Unable to resolve after max attempts

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- GitHub account with a personal access token
- Anthropic API key (Claude)
- Local PyTorch repository clone
- Claude CLI installed

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/sladyn98/pytorch-issue-agent.git
cd pytorch-issue-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Environment Variables

```bash
export GITHUB_TOKEN="ghp_your_github_token_here"
export ANTHROPIC_API_KEY="sk-ant-api03-your_anthropic_key_here"
```

**GitHub Token Permissions Required:**
- `repo` (Full repository access)
- `workflow` (Workflow permissions) 
- `user` (User information access)

### 3. Clone PyTorch Repository

```bash
# Clone PyTorch to your local machine  
git clone https://github.com/pytorch/pytorch.git /path/to/pytorch
```

### 4. Run the Agent

```bash
# Basic usage - fix issue #144701
python main.py 144701 --local-repo-path /path/to/pytorch

# With custom configuration
python main.py 144701 --local-repo-path /path/to/pytorch --config custom_config.json

# Dry run mode (no actual changes)
python main.py 144701 --local-repo-path /path/to/pytorch --dry-run
```

## 📋 Command Line Options

```bash
python main.py <issue_number> [OPTIONS]

Arguments:
  issue_number              GitHub issue number to fix

Options:
  --repo TEXT              Repository name (default: pytorch/pytorch)
  --local-repo-path TEXT   Path to local PyTorch repository (REQUIRED)
  --config TEXT            Path to config file
  --log-level TEXT         Log level (DEBUG, INFO, WARNING, ERROR)
  --dry-run               Run without making changes
  --help                   Show help message
```

## 🔧 Configuration

Create a `config.json` file to customize the agent behavior:

```json
{
  "agent": {
    "max_attempts": 3,
    "monitoring_interval": 18000,
    "state_file": "agent_state.json",
    "backup_interval": 300
  },
  "claude": {
    "model": "claude-3-sonnet-20240229",
    "max_tokens": 8192,
    "timeout": 300
  },
  "mcp": {
    "github_server_command": ["python", "-m", "mcp_github"]
  }
}
```

## 🎯 How It Works

### 1. Issue Analysis Phase
```
FETCHING → ANALYZING
```
- Fetches issue details from GitHub
- Analyzes issue complexity and categorization  
- Searches for related code files and patterns

### 2. Code Fixing Phase
```
ANALYZING → FIXING
```
- Creates a new branch for the fix
- Runs Claude CLI with detailed prompts
- Makes direct modifications to the codebase
- Commits changes with descriptive messages

### 3. Pull Request Phase
```
FIXING → CREATING_PR → MONITORING
```
- Pushes branch to GitHub (fork or origin)
- Generates comprehensive PR description
- Creates pull request linking to original issue
- Monitors for review comments and test results

### 4. State Machine
```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  FETCHING   │───▶│  ANALYZING  │───▶│   FIXING    │
└─────────────┘    └─────────────┘    └─────────────┘
                                             │
                                             ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│ MONITORING  │◀───│ CREATING_PR │◀───│      │      │
└─────────────┘    └─────────────┘    └─────────────┘
       │                                     │
       ▼                                     ▼
┌─────────────┐                      ┌─────────────┐
│ COMPLETED   │                      │   FAILED    │
└─────────────┘                      └─────────────┘
```

## 📝 Example Usage

### Successful Run Output
```bash
$ python main.py 144701 --local-repo-path /Users/username/pytorch

2025-06-15 00:00:01 [issue-144701] INFO: Starting PyTorch Issue Fixing Agent
2025-06-15 00:00:02 [issue-144701] INFO: State transition: fetching -> analyzing
2025-06-15 00:00:05 [issue-144701] INFO: Issue analysis completed
2025-06-15 00:00:05 [issue-144701] INFO: State transition: analyzing -> fixing
2025-06-15 00:00:10 [issue-144701] INFO: Created branch: fix-issue-144701-attempt-1
2025-06-15 00:00:15 [issue-144701] INFO: Claude CLI completed successfully
2025-06-15 00:00:16 [issue-144701] INFO: Committed changes: Fix issue #144701
2025-06-15 00:00:16 [issue-144701] INFO: Fix applied to 1 files
2025-06-15 00:00:16 [issue-144701] INFO: State transition: fixing -> creating_pr
2025-06-15 00:00:20 [issue-144701] INFO: Pushed branch: fix-issue-144701-attempt-1
2025-06-15 00:00:25 [issue-144701] INFO: Created pull request: #156013
2025-06-15 00:00:25 [issue-144701] INFO: Issue #144701 completed successfully!
```

## 🛡️ Safety Features

- **Dry Run Mode**: Test the agent without making actual changes
- **State Persistence**: Resumes from where it left off if interrupted
- **Error Recovery**: Automatically retries failed operations
- **Change Isolation**: Works in separate branches to avoid conflicts
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

## 🔍 Monitoring and Debugging

### State File
The agent maintains its state in `agent_state.json`:
```json
{
  "issue_number": 144701,
  "current_state": "fixing",
  "context": {
    "branch_name": "fix-issue-144701-attempt-1",
    "fix_attempt_count": 1,
    "generated_files": ["torch/distributed/pipelining/schedules.py"],
    "error_history": []
  }
}
```

### Log Analysis
```bash
# View recent activity
tail -f pytorch_agent.log

# Search for errors
grep -i error pytorch_agent.log

# Filter by state transitions
grep "State transition" pytorch_agent.log
```

## 🚨 Troubleshooting

### Common Issues

#### 1. **API Key Issues**
```bash
Error: Invalid API key · Fix external API key
```
**Solution**: Verify your `ANTHROPIC_API_KEY` is correctly set and valid.

#### 2. **Branch Creation Failed**
```bash
Error: Failed to create branch fix-issue-144701-attempt-1
```
**Solution**: Ensure the local repository path is correct and you have write permissions.

#### 3. **PR Creation Failed**
```bash
Error: Failed to create PR: Tool call failed: Not Found
```
**Solution**: Verify your GitHub token has `repo` permissions and you have a fork of the repository.

#### 4. **Claude CLI Failed**
```bash
Error: Claude CLI failed with return code 1
```
**Solution**: Check that Claude CLI is installed and your API key is valid.

### Debug Mode
```bash
python main.py 144701 --local-repo-path /path/to/pytorch --log-level DEBUG
```

## 🏗️ Architecture

### Core Components

- **`agent/controller.py`** - Main orchestration and state management
- **`agent/workflow.py`** - State machine and transition logic  
- **`claude/client.py`** - Claude AI integration and prompt management
- **`mcp/github_client.py`** - GitHub API operations via MCP
- **`utils/git_ops.py`** - Local git repository operations
- **`utils/local_ops.py`** - File system operations

### Dependencies

- **Anthropic Claude** - AI-powered code analysis and generation
- **GitHub MCP Server** - Secure GitHub API operations
- **Claude CLI** - Direct codebase modification capabilities
- **GitPython** - Git repository management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Commit your changes: `git commit -am 'Add feature'`
5. Push to the branch: `git push origin feature-name`
6. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **PyTorch Team** - For the amazing framework and open source community
- **Anthropic** - For Claude AI and the powerful language models
- **MCP Protocol** - For secure and standardized AI-tool interactions

---

**⚡ Ready to fix some PyTorch issues? Let's get started!**

```bash
python main.py <issue_number> --local-repo-path /path/to/pytorch
```

## ✅ **Validation Results**

The agent has been successfully validated with **real PyTorch issue #144701**:

- **✅ Issue Analysis**: Successfully analyzed complex pipelining requirements
- **✅ Code Generation**: Claude CLI made comprehensive updates to schedule classes  
- **✅ Git Operations**: Branch creation, commits, and push operations working
- **✅ PR Creation**: [PR #156013](https://github.com/pytorch/pytorch/pull/156013) successfully created
- **✅ Monitoring Setup**: PyTorch HUD integration installed and monitoring loop functional
- **⚡ Real-world Success**: Demonstrates end-to-end capability on actual PyTorch codebase

## 🐳 Docker Deployment

For production deployment, use the provided Docker configuration:

### Oracle Cloud Deployment

1. Navigate to deployment directory:
```bash
cd deployment-examples/oracle
```

2. Set environment variables:
```bash
export ANTHROPIC_API_KEY="your-api-key"
export GITHUB_TOKEN="your-github-token"
export GITHUB_USERNAME="your-username"
```

3. Deploy for a specific issue:
```bash
./deploy.sh 149534
```

The deployment includes:
- **🐳 Containerized Environment**: Isolated execution with all dependencies
- **📊 Persistent State**: Volume mounting for state preservation
- **🔄 Auto-restart**: Automatic container restart on failure
- **📋 Log Monitoring**: Real-time log streaming and monitoring

### Manual Docker Commands

```bash
# Build the image
docker build -t pytorch-issue-agent .

# Run for a specific issue
docker run -d \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_USERNAME="$GITHUB_USERNAME" \
  -v pytorch-repo:/pytorch \
  -v agent-state:/app/state \
  pytorch-issue-agent python main.py 149534 --local-repo-path /pytorch
```