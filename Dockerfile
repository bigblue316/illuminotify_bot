FROM python:3.9-alpine

# Create app directory
WORKDIR /usr/src/app

# copy files, requirements.txt and install dependencies
COPY requirements.txt .env main.py keywords.json .
RUN pip install -r requirements.txt

CMD ["python","main.py"]