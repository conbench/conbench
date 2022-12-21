
FROM python:3.11-slim-buster

RUN apt-get update && apt-get install -y -q --no-install-recommends \
        gnupg curl git jq moreutils ca-certificates unzip less tree pandoc \
    && curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add \
    && echo "deb [arch=amd64]  http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y -q --no-install-recommends \
        google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

RUN pip install pip --upgrade
RUN pip install selenium webdriver_manager && pip cache purge

# Install chrome driver manager into cache.
# This will then lead to e.g.
#    Driver [/root/.wdm/drivers/chromedriver/linux64/108.0.5359/chromedriver] found in cache
# during execution.
RUN python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"

COPY screenshot.py .