FROM python:3.10-slim

WORKDIR /workspace/tts

COPY requirements.txt .

# Create a non-root user and switch to it
RUN useradd -ms /bin/bash vscode
USER vscode

RUN pip install --no-cache-dir --user -r requirements.txt

# Ensure scripts in .local/bin are findable
ENV PATH="/home/vscode/.local/bin:${PATH}"

# This CMD is a placeholder. You'll replace it with your actual application command.
CMD ["python", "-m", "http.server", "8001"]
