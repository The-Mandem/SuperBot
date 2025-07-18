# SuperBot 🤖

A powerful Discord bot that combines multiple features including Instagram media downloading, API request handling, AI interactions via Google's Gemini, and custom response triggers.

## Features

### 🎯 Core Features

- **Instagram Media Downloader**: Automatically downloads and reposts media from Instagram links
- **API Request Handler (Postman)**: Make API requests directly from Discord
- **Gemini AI Integration**: Interact with Google's Gemini AI model
- **Custom Response Triggers**: Includes fun features like "no bqq" responses

### 🛠 Technical Features

- Environment-based configuration (Development/Production)
- Comprehensive error handling and logging
- Automatic deployment via GitHub Actions
- Systemd service integration for production

## Commands

- `!postman <request_type> <endpoint> <param:param_value>`: Make API requests
  - Example: `!postman get https://api.example.com/data "key:value" "auth:bearer-token"`
  - Supported methods: GET, POST, PUT, DELETE

- `!gemini <prompt>`: Interact with Gemini AI
  - Example: `!gemini What is the capital of France?`

## Setup & Development

### Prerequisites

- Python 3.11+
- Discord Bot Token
- Google Gemini API Key
- Git

### Local Development Setup

1. Clone the repository:

```bash
git clone https://github.com/The-Mandem/SuperBot.git
cd SuperBot
```

2. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development tools
```

4. Create a `.env` file:

```env
DISCORD_TOKEN_DEV=your_dev_bot_token
DISCORD_TOKEN_PROD=your_prod_bot_token
GEMINI_KEY=your_gemini_api_key
```

5. Run the bot:

```bash
python src/main.py --dev  # Development mode
python src/main.py --prod # Production mode
```

### Development Guidelines

#### Code Style

The project uses Ruff for linting and formatting. Pre-commit hooks are configured to ensure code quality:

```bash
pip install pre-commit
pre-commit install
```

#### Adding New Features

1. Create a new feature file in `src/features/`
2. Implement the feature class with `__init__` and `setup` methods
3. Register the feature in `main.py`

### Production Deployment

The bot uses GitHub Actions for automated deployment to a Raspberry Pi. Required secrets:

- `PI_HOST`: Raspberry Pi hostname/IP
- `PI_USER`: SSH username
- `PI_SSH_KEY`: SSH private key
- `PI_PORT`: SSH port (optional, defaults to 22)
- `BOT_REPO_PATH`: Path to bot directory on Pi
- `SYSTEMD_SERVICE_NAME`: Name of systemd service

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Support

For issues and feature requests, please use the GitHub Issues system.
