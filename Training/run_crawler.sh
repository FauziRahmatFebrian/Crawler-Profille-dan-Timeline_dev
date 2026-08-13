#!/bin/bash
cd /home/support/crawler-instagram
source venv/bin/activate
python main.py >> crawler.log 2>&1

