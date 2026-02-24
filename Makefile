# Makefile for TQQQ Auto-Trading System

# Default shell
SHELL := /bin/bash

# Python interpreter
PYTHON := python3
PIP := pip3

# Virtual environment directory
VENV_DIR := venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip

# Source code directory
SRC_DIR := code

# Default target
.PHONY: all
all: help

# Help command
.PHONY: help
help:
	@echo "TQQQ Auto-Trading System Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make run        - Run the trading bot (once)"
	@echo "  make start      - Start the scheduler in background (nohup)"
	@echo "  make stop       - Stop the background scheduler"
	@echo "  make status     - Check if the scheduler is running"
	@echo "  make logs       - Tail the logs"
	@echo "  make clean      - Remove virtual environment and temporary files"
	@echo "  make test       - Run tests (if any)"
	@echo ""

# Setup environment
.PHONY: setup
setup:
	@echo "Creating virtual environment in $(VENV_DIR)..."
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "Upgrading pip..."
	@$(VENV_PIP) install --upgrade pip
	@echo "Installing dependencies..."
	@$(VENV_PIP) install -r $(SRC_DIR)/requirements.txt
	@echo "Setup complete. Virtual environment is ready."

# Run the bot once (foreground)
.PHONY: run
run:
	@if [ ! -d "$(VENV_DIR)" ]; then echo "Virtual environment not found. Please run 'make setup' first."; exit 1; fi
	@echo "Running TQQQ strategy..."
	@$(VENV_PYTHON) $(SRC_DIR)/run.py

# Start the scheduler in background
.PHONY: start
start:
	@if [ ! -d "$(VENV_DIR)" ]; then echo "Virtual environment not found. Please run 'make setup' first."; exit 1; fi
	@if pgrep -f "$(SRC_DIR)/run.py" > /dev/null; then \
		echo "Scheduler is already running."; \
	else \
		echo "Starting scheduler in background..."; \
		nohup $(VENV_PYTHON) $(SRC_DIR)/run.py > $(SRC_DIR)/logs/scheduler.log 2>&1 & \
		echo "Scheduler started. PID: $$(pgrep -f "$(SRC_DIR)/run.py")"; \
		echo "Logs are being written to $(SRC_DIR)/logs/scheduler.log"; \
	fi

# Stop the background scheduler
.PHONY: stop
stop:
	@echo "Stopping scheduler..."
	@pkill -f "$(SRC_DIR)/run.py" || echo "Scheduler not running."
	@echo "Stopped."

# Check status
.PHONY: status
status:
	@if pgrep -f "$(SRC_DIR)/run.py" > /dev/null; then \
		echo "Scheduler is RUNNING (PID: $$(pgrep -f "$(SRC_DIR)/run.py"))"; \
	else \
		echo "Scheduler is STOPPED"; \
	fi

# Tail logs
.PHONY: logs
logs:
	@echo "Tailing logs (Ctrl+C to exit)..."
	@tail -f $(SRC_DIR)/logs/strategy.log $(SRC_DIR)/logs/scheduler.log 2>/dev/null || echo "Log files not found yet."

# Clean environment
.PHONY: clean
clean:
	@echo "Cleaning up..."
	@rm -rf $(VENV_DIR)
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@echo "Clean complete."

# Run tests (placeholder)
.PHONY: test
test:
	@if [ ! -d "$(VENV_DIR)" ]; then echo "Virtual environment not found. Please run 'make setup' first."; exit 1; fi
	@echo "Running tests..."
	@# $(VENV_PYTHON) -m pytest tests/
	@echo "No tests configured yet."
