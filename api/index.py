from flask import Flask, request, jsonify, redirect, send_file
from flask_cors import CORS

import requests
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
import time
from urllib.parse import urlencode

import base64
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

app = Flask(__name__)

BRFER_LOGO_BASE64 = "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ังก์0AIFj0AIFj0S3Abังก์0AIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEAIEx311qjZAAAAA"


def gerar_pdf_proposta(dados_front, dados_orcamento, contato, orcamento_id):
    """Gera localmente uma proposta comercial em PDF alinhada 100% com o padrão Tiny ERP."""

    cliente = dados_front.get("cliente") or {}
    endereco = dados_front.get("endereco") or {}

    def primeiro_valor(*valores):
        for valor in valores:
            if valor not in (None, ""):
                return valor
        return ""

    def float_seguro(valor, padrao=0.0):
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return padrao

    def numero_pt(valor):
        return f"{float_seguro(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def texto(valor):
        return str(valor or "").strip()

    def escape_html(valor):
        return (
            texto(valor)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def endereco_formatado():
        partes = []
        logradouro = texto(endereco.get("logradouro"))
        numero = texto(endereco.get("numero"))
        complemento = texto(endereco.get("complemento"))
        bairro = texto(endereco.get("bairro"))
        cidade = texto(endereco.get("cidade"))
        uf = texto(endereco.get("uf"))
        cep = texto(endereco.get("cep"))

        if logradouro:
            linha = logradouro
            if numero:
                linha += f", Nº {numero}"
            if complemento:
                linha += f", {complemento}"
            if bairro:
                linha += f", {bairro}"
            partes.append(linha)

        cidade_linha = ""
        if cidade:
            cidade_linha = cidade
        if uf:
            cidade_linha += f" - {uf}" if cidade_linha else uf
        if cep:
            cidade_linha += f" / CEP: {cep}"
        if cidade_linha:
            partes.append(cidade_linha)

        return partes

    # ----------------------- ESTILOS E MARGENS ---------------------------
    # Margens de 15mm => Largura útil exata = 210mm - 30mm = 180mm
    LARGURA_UTIL = 180 * mm

    styles = getSampleStyleSheet()
    
    normal = ParagraphStyle(
        "PropostaNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#222222"),
    )
    
    title_style = ParagraphStyle(
        "PropostaTitle",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        alignment=TA_CENTER,
    )
    
    table_header = ParagraphStyle(
        "PropostaTableHeader",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#333333"),
    )
    
    table_left = ParagraphStyle(
        "PropostaTableLeft",
        parent=normal,
        fontSize=8,
        leading=10,
    )
    
    table_center = ParagraphStyle(
        "PropostaTableCenter",
        parent=table_left,
        alignment=TA_CENTER,
    )
    
    table_right = ParagraphStyle(
        "PropostaTableRight",
        parent=table_left,
        alignment=TA_RIGHT,
    )
    
    empresa_style = ParagraphStyle(
        "EmpresaHeader",
        parent=normal,
        fontSize=8,
        leading=10,
        alignment=TA_RIGHT,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=10 * mm,
        bottomMargin=15 * mm,
        title=f"Proposta Comercial {orcamento_id}",
        author="BRFER Comércio de Ferramentas LTDA",
    )

    story = []

    # ----------------------- CABEÇALHO (180mm total) ---------------------------
    logo_stream = BytesIO(base64.b64decode(BRFER_LOGO_BASE64))
    logo = Image(logo_stream, width=42 * mm, height=25 * mm)

    empresa_html = (
        "<b>BRFER COMÉRCIO DE FERRAMENTAS LTDA</b><br/>"
        "CNPJ: 40.954.410/0001-96<br/>"
        "www.brfer.com.br<br/>"
        "Fone: (11) 4362-5151<br/>"
        "Rua Coronel Francisco Rodrigues Seckler, 53, galpão<br/>"
        "Paulicéia, São Bernardo do Campo - SP - CEP: 09693-050"
    )

    header = Table(
        [[logo, Paragraph(empresa_html, empresa_style)]],
        colWidths=[45 * mm, 135 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    numero_proposta = primeiro_valor(
        dados_orcamento.get("numeroProposta"),
        dados_orcamento.get("numero"),
        orcamento_id,
    )
    story.append(Paragraph(
        f"Proposta Comercial Nº {escape_html(numero_proposta)}",
        title_style,
    ))
    story.append(Spacer(1, 4 * mm))

    # ------------------- CLIENTE / ENDEREÇO (180mm) ----------------------
    nome_cliente = texto(
        primeiro_valor(
            cliente.get("razao_social"),
            cliente.get("nome"),
            "Cliente",
        )
    )
    documento = texto(cliente.get("cpf_cnpj"))
    endereco_linhas = endereco_formatado()

    telefone = texto(primeiro_valor(contato.get("telefone"), cliente.get("telefone")))
    celular = texto(primeiro_valor(contato.get("celular"), contato.get("telefoneCelular"), cliente.get("celular")))
    email = texto(primeiro_valor(contato.get("email"), cliente.get("email")))

    dados_endereco = [
        [Paragraph("<b>Para:</b>", normal)],
        [Paragraph(f"<b>{escape_html(nome_cliente)}</b>", normal)],
    ]
    if documento:
        dados_endereco.append([Paragraph(f"<b>CPF/CNPJ:</b> {escape_html(documento)}", normal)])
        
    for linha in endereco_linhas:
        dados_endereco.append([Paragraph(escape_html(linha), normal)])

    contato_linha = []
    if telefone:
        contato_linha.append(f"Fone: {escape_html(telefone)}")
    if celular and celular != telefone:
        contato_linha.append(f"Celular: {escape_html(celular)}")
    if email:
        contato_linha.append(f"E-mail: {escape_html(email)}")
    if contato_linha:
        dados_endereco.append([Paragraph(" | ".join(contato_linha), normal)])

    endereco_box = Table(
        dados_endereco,
        colWidths=[LARGURA_UTIL],
    )
    endereco_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#777777")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(endereco_box)
    story.append(Spacer(1, 4 * mm))

    # ------------------- INTRODUÇÃO ----------------------
    introducao = dados_front.get("introducao") or (
        "Prezado cliente, seguem abaixo proposta comercial com "
        "pagamento à vista com desconto e nossos dados bancários:\n\n"
        "Segue nossos dados bancários:\n"
        "BRFER Comércio de Ferramentas LTDA\n"
        "CNPJ 40.954.410/0001-96\n"
        "Banco: 341 – Itaú\n"
        "Agência: 8811\n"
        "Conta Corrente: 99874-2\n\n"
        "Se preferir, o pagamento pode ser realizado via PIX, a chave "
        "é o nosso CNPJ"
    )

    for bloco in str(introducao).split("\n\n"):
        linhas = str(bloco).split("\n")
        html_bloco = "<br/>".join(escape_html(linha) for linha in linhas)
        story.append(Paragraph(html_bloco, normal))
        story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Itens de produto ou serviço</b>", normal))
    story.append(Spacer(1, 1.5 * mm))

    # ------------------- ITENS (180mm Total) ----------------------
    itens = dados_orcamento.get("itens")
    if not isinstance(itens, list) or not itens:
        itens = []
        for item in dados_front.get("carrinho") or []:
            itens.append({
                "produto": {
                    "descricao": item.get("descricao") or item.get("nome"),
                    "sku": item.get("sku"),
                },
                "quantidade": item.get("quantidade", 1),
                "valorUnitario": item.get("preco_unitario", 0),
                "descrComplementarOrc": item.get("descricao") or item.get("nome"),
            })

    corpo_itens = [[
        Paragraph("<b>Nº</b>", table_header),
        Paragraph("<b>Item / Descrição</b>", table_header),
        Paragraph("<b>SKU</b>", table_header),
        Paragraph("<b>Qtd</b>", table_header),
        Paragraph("<b>Un</b>", table_header),
        Paragraph("<b>Preço un (R$)</b>", table_header),
        Paragraph("<b>Total (R$)</b>", table_header),
    ]]

    soma_quantidades = 0.0
    total_itens_calculado = 0.0

    for indice, item in enumerate(itens, start=1):
        produto = item.get("produto") or {}
        descricao = texto(
            primeiro_valor(
                produto.get("descricao"),
                item.get("descricao"),
                item.get("nome"),
                "Produto",
            )
        )
        sku = texto(primeiro_valor(produto.get("sku"), item.get("sku")))
        quantidade = float_seguro(item.get("quantidade"), 1.0)
        valor_unitario = float_seguro(
            item.get("valorUnitario"),
            float_seguro(item.get("preco_unitario")),
        )
        total_item = quantidade * valor_unitario
        soma_quantidades += quantidade
        total_itens_calculado += total_item

        complemento = texto(item.get("descrComplementarOrc"))
        descricao_html = escape_html(descricao)
        if complemento and complemento != descricao:
            descricao_html += (
                f"<br/><font color='#555555' size='7.5'>{escape_html(complemento)}</font>"
            )

        corpo_itens.append([
            Paragraph(str(indice), table_center),
            Paragraph(descricao_html, table_left),
            Paragraph(escape_html(sku), table_center),
            Paragraph(numero_pt(quantidade), table_center),
            Paragraph("UN", table_center),
            Paragraph(numero_pt(valor_unitario), table_right),
            Paragraph(numero_pt(total_item), table_right),
        ])

    subtotal = float_seguro(
        primeiro_valor(
            dados_orcamento.get("valorSubtotal"),
            dados_orcamento.get("valorTotal"),
            total_itens_calculado,
        )
    )
    total_proposta = float_seguro(
        primeiro_valor(
            dados_orcamento.get("valorTotal"),
            subtotal,
        )
    )

    # Linha final de soma
    corpo_itens.append([
        Paragraph(
            f"<b>Número de itens:</b> {len(itens)} &nbsp;&nbsp;&nbsp;&nbsp; "
            f"<b>Soma das quantidades:</b> {numero_pt(soma_quantidades)}",
            normal,
        ),
        "", "", "", "",
        Paragraph("<b>Total dos itens</b>", table_right),
        Paragraph(f"<b>R$ {numero_pt(subtotal)}</b>", table_right),
    ])

    # Colunas: 8 + 77 + 25 + 14 + 10 + 23 + 23 = 180mm
    colunas_itens = [8 * mm, 77 * mm, 25 * mm, 14 * mm, 10 * mm, 23 * mm, 23 * mm]

    tabela_itens = Table(
        corpo_itens,
        colWidths=colunas_itens,
        repeatRows=1,
        splitByRow=1,
    )
    tabela_itens.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -2), 0.5, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("SPAN", (0, -1), (4, -1)),
        ("BOX", (0, -1), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FAFAFA")),
    ]))
    story.append(tabela_itens)
    story.append(Spacer(1, 4 * mm))

    # ------------------- RESUMO DATA E TOTAL (180mm Total) ----------------------
    data_raw = primeiro_valor(
        dados_orcamento.get("data"),
        datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),
    )
    try:
        data_fmt = datetime.fromisoformat(str(data_raw)[:10]).strftime("%d/%m/%Y")
    except Exception:
        data_fmt = str(data_raw)

    resumo_data = Table([
        [
            Paragraph("<b>Data</b>", table_center),
            Paragraph("<b>Total dos itens</b>", table_right),
            Paragraph("<b>Total da proposta</b>", table_right),
        ],
        [
            Paragraph(escape_html(data_fmt), table_center),
            Paragraph(f"R$ {numero_pt(subtotal)}", table_right),
            Paragraph(f"<b>R$ {numero_pt(total_proposta)}</b>", table_right),
        ],
        ],
        colWidths=[50 * mm, 65 * mm, 65 * mm]
    )
    resumo_data.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(resumo_data)
    story.append(Spacer(1, 4 * mm))

    # ------------------- OBSERVAÇÕES (180mm Total) ----------------------
    observacoes = dados_front.get("observacoes") or (
        "Somos um E-COMMERCE, não reservamos estoque antes da aprovação do pagamento."
    )
    resumo = dados_front.get("resumo_carrinho") or {}
    total_carrinho = float_seguro(primeiro_valor(resumo.get("total"), subtotal))
    valor_avista = float_seguro(resumo.get("avista"))
    valor_3x = float_seguro(resumo.get("parcela_3x"))
    valor_12x = float_seguro(resumo.get("parcela_12x"))

    if not valor_avista:
        valor_avista = total_carrinho * 0.98

    pagamentos_html = (
        "<b>Condições de pagamento do carrinho:</b><br/>"
        f"• Total do carrinho: R$ {numero_pt(total_carrinho)}<br/>"
        f"• Pagamento à vista com desconto: R$ {numero_pt(valor_avista)}<br/>"
        f"• 3x de R$ {numero_pt(valor_3x)} sem juros<br/>"
        f"• 12x de R$ {numero_pt(valor_12x)} com juros no cartão."
    )
    observacoes_html = escape_html(observacoes).replace("\n", "<br/>")

    observacoes_box = Table(
        [[Paragraph(f"{observacoes_html}<br/><br/>{pagamentos_html}", normal)]],
        colWidths=[LARGURA_UTIL]
    )
    observacoes_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#777777")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(Paragraph("<b>Observações</b>", normal))
    story.append(Spacer(1, 1.5 * mm))
    story.append(observacoes_box)
    story.append(Spacer(1, 6 * mm))

    # ------------------- RODAPÉ / ASSINATURA ----------------------
    story.append(Paragraph("Atenciosamente,", normal))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("<b>Departamento de Vendas</b>", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)

TINY_API_URL = "https://api.tiny.com.br/public-api/v3"

TINY_AUTH_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/auth"
)

TINY_TOKEN_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/token"
)

TINY_CLIENT_ID = os.environ.get(
    "TINY_CLIENT_ID"
)

TINY_CLIENT_SECRET = os.environ.get(
    "TINY_CLIENT_SECRET"
)

TINY_REDIRECT_URI = os.environ.get(
    "TINY_REDIRECT_URI"
)


REDIS_URL = (
    os.environ.get("UPSTASH_REDIS_REST_URL")
    or
    os.environ.get("KV_REST_API_URL")
)

REDIS_TOKEN = (
    os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    or
    os.environ.get("KV_REST_API_TOKEN")
)

TINY_TOKEN_KEY = "tiny:oauth:tokens"

OAUTH_STATE_KEY = "tiny:oauth:state"
TINY_REFRESH_LOCK_KEY = "tiny:oauth:refresh-lock"
TINY_REFRESH_LOCK_TTL = 60
TINY_REFRESH_WAIT_SECONDS = 12

class TinyAPIError(Exception):

    def __init__(
        self,
        mensagem,
        status=None,
        resposta=None
    ):

        super().__init__(mensagem)

        self.mensagem = mensagem
        self.status = status
        self.resposta = resposta

def redis_disponivel():

    return bool(
        REDIS_URL
        and REDIS_TOKEN
    )


def redis_request(
    comando,
    *argumentos
):

    if not redis_disponivel():

        raise RuntimeError(
            "Upstash Redis não está configurado."
        )


    url = REDIS_URL.rstrip("/") + "/"


    payload = [
        comando,
        *argumentos
    ]


    response = requests.post(
        url,
        headers={
            "Authorization":
                f"Bearer {REDIS_TOKEN}",

            "Content-Type":
                "application/json"
        },
        json=payload,
        timeout=10
    )


    if not response.ok:

        raise RuntimeError(
            "Erro ao acessar Upstash Redis: "
            f"HTTP {response.status_code} "
            f"{response.text}"
        )


    dados = response.json()

    return dados.get("result")


def redis_get(chave):

    return redis_request(
        "GET",
        chave
    )


def redis_set(
    chave,
    valor,
    expiracao=None
):

    if expiracao:

        return redis_request(
            "SET",
            chave,
            valor,
            "EX",
            str(expiracao)
        )


    return redis_request(
        "SET",
        chave,
        valor
    )


def redis_delete(chave):

    return redis_request(
        "DEL",
        chave
    )

def carregar_tokens():

    valor = redis_get(
        TINY_TOKEN_KEY
    )


    if not valor:

        return None


    try:

        return json.loads(
            valor
        )

    except Exception:

        print(
            "ERRO: tokens armazenados no Redis "
            "não são um JSON válido."
        )

        return None


def salvar_tokens(
    access_token,
    refresh_token,
    expires_in
):

    agora = int(
        time.time()
    )


    # Margem de segurança de 60 segundos.
    expires_at = (
        agora
        + int(expires_in or 3600)
        - 60
    )


    dados = {

        "access_token":
            access_token,

        "refresh_token":
            refresh_token,

        "expires_at":
            expires_at,

        "updated_at":
            agora
    }


    redis_set(

        TINY_TOKEN_KEY,

        json.dumps(
            dados
        )
    )


    print(
        "Tokens OAuth salvos no Upstash Redis."
    )

def headers_tiny(
    access_token
):

    return {

        "Authorization":
            f"Bearer {access_token}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }

def resposta_json(
    response
):

    try:

        return response.json()

    except Exception:

        return response.text
    
@app.route(
    "/api/oauth/autorizar",
    methods=["GET"]
)
def oauth_autorizar():

    if not TINY_CLIENT_ID:

        return jsonify({

            "erro":
                "TINY_CLIENT_ID não configurado na Vercel."

        }), 500


    if not TINY_CLIENT_SECRET:

        return jsonify({

            "erro":
                "TINY_CLIENT_SECRET não configurado na Vercel."

        }), 500


    if not TINY_REDIRECT_URI:

        return jsonify({

            "erro":
                "TINY_REDIRECT_URI não configurado na Vercel."

        }), 500


    if not redis_disponivel():

        return jsonify({

            "erro":
                "Upstash Redis não configurado.",

            "REDIS_URL":
                bool(REDIS_URL),

            "REDIS_TOKEN":
                bool(REDIS_TOKEN)

        }), 500

    state = secrets.token_urlsafe(
        32
    )


    redis_set(
        OAUTH_STATE_KEY,
        state,
        600
    )


    parametros = {

        "client_id":
            TINY_CLIENT_ID,

        "redirect_uri":
            TINY_REDIRECT_URI,

        "response_type":
            "code",

        "state":
            state
    }


    url = (
        TINY_AUTH_URL
        + "?"
        + urlencode(parametros)
    )


    print(
        "Iniciando autorização OAuth Tiny."
    )


    return redirect(
        url
    )

@app.route(
    "/api/oauth/callback",
    methods=["GET"]
)
def oauth_callback():

    codigo = request.args.get(
        "code"
    )

    state = request.args.get(
        "state"
    )

    erro = request.args.get(
        "error"
    )


    if erro:

        return jsonify({

            "erro":
                "O Tiny recusou a autorização.",

            "detalhes":
                erro,

            "descricao":
                request.args.get(
                    "error_description"
                )

        }), 400


    if not codigo:

        return jsonify({

            "erro":
                "Código de autorização não recebido."

        }), 400


    if not state:

        return jsonify({

            "erro":
                "State OAuth não recebido."

        }), 400

    state_salvo = redis_get(
        OAUTH_STATE_KEY
    )


    if not state_salvo:

        return jsonify({

            "erro":
                "State OAuth expirado ou inexistente.",

            "orientacao":
                "Acesse /api/oauth/autorizar novamente."

        }), 400


    if not secrets.compare_digest(
        str(state_salvo),
        str(state)
    ):

        return jsonify({

            "erro":
                "State OAuth inválido."

        }), 400

    redis_delete(
        OAUTH_STATE_KEY
    )

    try:

        response = requests.post(

            TINY_TOKEN_URL,

            data={

                "grant_type":
                    "authorization_code",

                "client_id":
                    TINY_CLIENT_ID,

                "client_secret":
                    TINY_CLIENT_SECRET,

                "redirect_uri":
                    TINY_REDIRECT_URI,

                "code":
                    codigo
            },

            headers={

                "Accept":
                    "application/json",

                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=30
        )


        dados = resposta_json(
            response
        )


        print(
            "OAuth Tiny HTTP:",
            response.status_code
        )


        if not response.ok:

            print(
                "Resposta OAuth:",
                dados
            )


            return jsonify({

                "erro":
                    "Tiny recusou a troca do código.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), 502


        access_token = dados.get(
            "access_token"
        )

        refresh_token = dados.get(
            "refresh_token"
        )

        expires_in = dados.get(
            "expires_in",
            3600
        )


        if not access_token:

            return jsonify({

                "erro":
                    "Tiny não retornou access_token.",

                "resposta_tiny":
                    dados

            }), 502


        if not refresh_token:

            return jsonify({

                "erro":
                    "Tiny não retornou refresh_token.",

                "resposta_tiny":
                    dados

            }), 502
        
        salvar_tokens(

            access_token,

            refresh_token,

            expires_in
        )


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                (
                    "Aplicação autorizada com sucesso. "
                    "Os tokens foram armazenados "
                    "automaticamente no Upstash Redis."
                ),

            "expira_em_segundos":
                expires_in,

            "proximo_passo":
                (
                    "A integração já pode utilizar "
                    "/api/gerar-proposta."
                )

        }), 200


    except requests.RequestException as e:

        return jsonify({

            "erro":
                "Erro de comunicação com o OAuth do Tiny.",

            "detalhes":
                str(e)

        }), 502

def renovar_access_token(
    tokens
):

    tokens = tokens or {}

    refresh_token = tokens.get(
        "refresh_token"
    )

    if not refresh_token:
        raise TinyAPIError(
            "Refresh token não encontrado. Autorize novamente a aplicação no Tiny.",
            401,
            {
                "autorizacao":
                    "/api/oauth/autorizar"
            }
        )
    
    lock_token = secrets.token_urlsafe(32)
    lock_adquirido = False

    try:
        for _ in range(
            int(TINY_REFRESH_WAIT_SECONDS * 2)
        ):
            resultado_lock = redis_request(
                "SET",
                TINY_REFRESH_LOCK_KEY,
                lock_token,
                "NX",
                "EX",
                str(TINY_REFRESH_LOCK_TTL)
            )

            if resultado_lock == "OK":
                lock_adquirido = True

                print(
                    "Lock de renovação OAuth adquirido."
                )

                break

            time.sleep(0.5)

            tokens_atualizados = carregar_tokens()

            if not tokens_atualizados:
                continue

            novo_access = tokens_atualizados.get(
                "access_token"
            )

            novo_expires_at = int(
                tokens_atualizados.get(
                    "expires_at",
                    0
                )
            )

            if (
                novo_access
                and
                novo_access != tokens.get("access_token")
                and
                int(time.time()) < novo_expires_at
            ):
                print(
                    "Outra execução já renovou o OAuth. "
                    "Reutilizando o novo access token."
                )

                return {
                    "access_token":
                        novo_access,
                    "refresh_token":
                        tokens_atualizados.get(
                            "refresh_token"
                        ),
                    "expires_in":
                        max(
                            1,
                            novo_expires_at - int(time.time())
                        )
                }

        if not lock_adquirido:
            tokens_atualizados = carregar_tokens()

            if tokens_atualizados:
                novo_access = tokens_atualizados.get(
                    "access_token"
                )

                novo_expires_at = int(
                    tokens_atualizados.get(
                        "expires_at",
                        0
                    )
                )

                if (
                    novo_access
                    and
                    novo_access != tokens.get("access_token")
                    and
                    int(time.time()) < novo_expires_at
                ):
                    return {
                        "access_token":
                            novo_access,
                        "refresh_token":
                            tokens_atualizados.get(
                                "refresh_token"
                            ),
                        "expires_in":
                            max(
                                1,
                                novo_expires_at - int(time.time())
                            )
                    }

            raise TinyAPIError(
                "Outra requisição está renovando o acesso ao Tiny. "
                "Tente novamente em alguns segundos.",
                503,
                {
                    "motivo":
                        "lock_de_renovacao_oauth"
                }
            )

        tokens_atuais = carregar_tokens() or {}

        access_atual = tokens_atuais.get(
            "access_token"
        )

        expires_at_atual = int(
            tokens_atuais.get(
                "expires_at",
                0
            )
        )

        refresh_atual = tokens_atuais.get(
            "refresh_token"
        )

        if (
            access_atual
            and
            int(time.time()) < expires_at_atual
            and
            access_atual != tokens.get("access_token")
        ):
            print(
                "Tokens já foram renovados por outra execução. "
                "Nenhum novo refresh será realizado."
            )

            return {
                "access_token":
                    access_atual,
                "refresh_token":
                    refresh_atual,
                "expires_in":
                    max(
                        1,
                        expires_at_atual - int(time.time())
                    )
            }

        refresh_token = refresh_atual or refresh_token

        if not refresh_token:
            raise TinyAPIError(
                "Refresh token não encontrado. Autorize novamente a aplicação no Tiny.",
                401,
                {
                    "autorizacao":
                        "/api/oauth/autorizar"
                }
            )

        response = requests.post(
            TINY_TOKEN_URL,
            data={
                "grant_type":
                    "refresh_token",
                "client_id":
                    TINY_CLIENT_ID,
                "client_secret":
                    TINY_CLIENT_SECRET,
                "refresh_token":
                    refresh_token
            },
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            timeout=30
        )

        dados = resposta_json(
            response
        )

        print(
            "Renovação OAuth Tiny HTTP:",
            response.status_code
        )

        if not response.ok:
            print(
                "Resposta OAuth refresh:",
                dados
            )

            texto_erro = json.dumps(
                dados,
                ensure_ascii=False
            ).lower()

            invalid_grant = (
                "invalid_grant" in texto_erro
                or
                "token is not active" in texto_erro
            )

            if invalid_grant:
                try:
                    redis_delete(
                        TINY_TOKEN_KEY
                    )
                except Exception as e:
                    print(
                        "Aviso: não foi possível remover os tokens "
                        "OAuth inválidos:",
                        str(e)
                    )

                raise TinyAPIError(
                    "O refresh token do Tiny não está mais ativo. "
                    "É necessário autorizar novamente a aplicação no Tiny.",
                    401,
                    {
                        "resposta_tiny":
                            dados,
                        "autorizacao":
                            "/api/oauth/autorizar"
                    }
                )

            raise TinyAPIError(
                "Não foi possível renovar o access token.",
                response.status_code,
                dados
            )

        novo_access_token = dados.get(
            "access_token"
        )
        novo_refresh_token = (
            dados.get(
                "refresh_token"
            )
            or
            refresh_token
        )

        expires_in = dados.get(
            "expires_in",
            3600
        )

        if not novo_access_token:
            raise TinyAPIError(
                "Tiny não retornou novo access_token.",
                502,
                dados
            )
        salvar_tokens(
            novo_access_token,
            novo_refresh_token,
            expires_in
        )

        print(
            "Renovação OAuth concluída e tokens atualizados no Redis."
        )

        return {
            "access_token":
                novo_access_token,
            "refresh_token":
                novo_refresh_token,
            "expires_in":
                expires_in
        }

    except requests.RequestException as e:
        raise TinyAPIError(
            "Erro de comunicação durante "
            "a renovação do token.",
            None,
            str(e)
        )

    finally:
        if lock_adquirido:
            try:
                redis_delete(
                    TINY_REFRESH_LOCK_KEY
                )

                print(
                    "Lock de renovação OAuth liberado."
                )

            except Exception as e:
                print(
                    "Aviso: não foi possível liberar o lock OAuth:",
                    str(e)
                )

def obter_access_token():

    tokens = carregar_tokens()


    if not tokens:

        raise TinyAPIError(

            "A aplicação ainda não foi autorizada no Tiny.",

            401,

            {
                "autorizacao":
                    "/api/oauth/autorizar"
            }
        )


    access_token = tokens.get(
        "access_token"
    )

    expires_at = int(
        tokens.get(
            "expires_at",
            0
        )
    )


    agora = int(
        time.time()
    )


    if (
        access_token
        and
        agora < expires_at
    ):

        return access_token


    print(
        "Access token expirado. Renovando..."
    )


    novos_tokens = renovar_access_token(
        tokens
    )


    return novos_tokens[
        "access_token"
    ]

def tiny_request(
    metodo,
    endpoint,
    **kwargs
):

    access_token = obter_access_token()


    response = requests.request(

        metodo,

        f"{TINY_API_URL}{endpoint}",

        headers=headers_tiny(
            access_token
        ),

        timeout=30,

        **kwargs
    )

    if response.status_code == 401:

        print(
            "Tiny retornou HTTP 401."
        )

        print(
            "Tentando renovar o access token..."
        )


        tokens = carregar_tokens()


        if not tokens:

            raise TinyAPIError(

                "Tokens OAuth não encontrados.",

                401,

                resposta_json(
                    response
                )
            )


        novos_tokens = renovar_access_token(
            tokens
        )


        response = requests.request(

            metodo,

            f"{TINY_API_URL}{endpoint}",

            headers=headers_tiny(

                novos_tokens[
                    "access_token"
                ]
            ),

            timeout=30,

            **kwargs
        )


    return response

def limpar_documento(
    valor
):

    if not valor:

        return ""


    return "".join(

        c

        for c in str(
            valor
        )

        if c.isdigit()
    )


def localizar_contato(
    cpf_cnpj,
    nome=None,
    busca_exaustiva=False
):

    documento = limpar_documento(cpf_cnpj)

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    situacoes = [None, "B", "A", "I", "E"]
    vistos = set()

    for situacao in situacoes:

        params = {
            "cpfCnpj": documento,
            "limit": 100,
            "offset": 0
        }

        if situacao:
            params["situacao"] = situacao

        response = tiny_request(
            "GET",
            "/contatos",
            params=params
        )

        dados = resposta_json(response)

        print(
            "Consulta contato por CPF/CNPJ:",
            documento,
            "situação:",
            situacao or "todas",
            "HTTP:",
            response.status_code
        )

        if not response.ok:
            if situacao:
                continue

            raise TinyAPIError(
                "Erro ao consultar contato no Tiny.",
                response.status_code,
                dados
            )

        contatos = dados.get(
            "itens",
            []
        )

        if not isinstance(contatos, list):
            contatos = []

        for contato in contatos:

            contato_id = contato.get("id")

            if contato_id in vistos:
                continue

            vistos.add(contato_id)

            documento_tiny = limpar_documento(
                contato.get("cpfCnpj")
            )

            if documento_tiny == documento:
                return contato

    if nome:

        response = tiny_request(
            "GET",
            "/contatos",
            params={
                "nome": nome,
                "limit": 100,
                "offset": 0
            }
        )

        dados = resposta_json(response)

        print(
            "Fallback consulta contato por nome:",
            nome,
            "HTTP:",
            response.status_code
        )

        if response.ok:

            contatos = dados.get(
                "itens",
                []
            )

            if isinstance(contatos, list):

                for contato in contatos:

                    documento_tiny = limpar_documento(
                        contato.get("cpfCnpj")
                    )

                    if documento_tiny == documento:
                        return contato

    if busca_exaustiva:

        limit = 100
        offset = 0
        total = None
        max_paginas = 1000

        for _ in range(max_paginas):

            response = tiny_request(
                "GET",
                "/contatos",
                params={
                    "limit": limit,
                    "offset": offset
                }
            )

            dados = resposta_json(response)

            print(
                "Busca exaustiva de contato:",
                "offset=",
                offset,
                "HTTP=",
                response.status_code
            )

            if not response.ok:

                raise TinyAPIError(
                    "Erro ao percorrer contatos do Tiny para localizar o CPF/CNPJ.",
                    response.status_code,
                    dados
                )

            contatos = dados.get(
                "itens",
                []
            )

            if not isinstance(contatos, list):
                contatos = []

            for contato in contatos:

                documento_tiny = limpar_documento(
                    contato.get("cpfCnpj")
                )

                if documento_tiny == documento:

                    print(
                        "Contato localizado na busca exaustiva. ID:",
                        contato.get("id")
                    )

                    return contato

            paginacao = dados.get(
                "paginacao",
                {}
            )

            if isinstance(paginacao, dict):

                try:
                    total = int(
                        paginacao.get("total")
                    )
                except (TypeError, ValueError):
                    total = None

            if not contatos:
                break

            offset += len(contatos)

            if total is not None and offset >= total:
                break

            if len(contatos) < limit and total is None:
                break

    return None

def criar_contato(dados_front):

    cliente = dados_front.get(
        "cliente",
        {}
    )

    endereco = dados_front.get(
        "endereco",
        {}
    )

    documento = limpar_documento(
        cliente.get("cpf_cnpj")
    )

    nome = (
        cliente.get("nome")
        or cliente.get("razao_social")
        or "Cliente da loja"
    )

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    if not nome:
        raise TinyAPIError(
            "Nome do cliente não informado."
        )

    codigo = f"WEB-{documento}"

    endereco_tiny = {
        "endereco": endereco.get("logradouro"),
        "numero": endereco.get("numero"),
        "complemento": endereco.get("complemento"),
        "bairro": endereco.get("bairro"),
        "municipio": endereco.get("cidade"),
        "cep": endereco.get("cep"),
        "uf": endereco.get("uf"),
        "pais": "Brasil"
    }

    endereco_tiny = {
        chave: valor
        for chave, valor in endereco_tiny.items()
        if valor not in [None, ""]
    }

    payload = {
        "nome": nome,
        "codigo": codigo,
        "cpfCnpj": documento,
        "email": dados_front.get("email"),
        "telefone": dados_front.get("telefone"),
        "endereco": endereco_tiny,
        "observacoesDoContato": "Contato criado automaticamente pela solicitação de proposta comercial via site."
    }

    payload = {
        chave: valor
        for chave, valor in payload.items()
        if valor not in [None, ""]
    }

    print("")
    print("========================================")
    print("CRIANDO CONTATO NO TINY")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("========================================")

    response = tiny_request(
        "POST",
        "/contatos",
        json=payload
    )

    dados = resposta_json(response)

    print(
        "POST /contatos:",
        response.status_code
    )
    print(
        "Resposta criação contato:",
        dados
    )

    if not response.ok:

        texto_erro = json.dumps(
            dados,
            ensure_ascii=False
        ).lower()

        documento_duplicado = (
            response.status_code == 400
            and (
                "já existe" in texto_erro
                or "ja existe" in texto_erro
                or "already exists" in texto_erro
            )
            and (
                "cnpj" in texto_erro
                or "cpf" in texto_erro
            )
        )

        if documento_duplicado:

            print(
                "Tiny informou que o CPF/CNPJ já existe. "
                "Tentando localizar o contato existente..."
            )

            contato_existente = localizar_contato(
                documento,
                nome,
                busca_exaustiva=True
            )

            if contato_existente:

                contato_id = contato_existente.get(
                    "id"
                )

                if contato_id:
                    print(
                        "Contato existente recuperado após "
                        "erro de duplicidade. ID:",
                        contato_id
                    )

                    return {
                        "id": contato_id,
                        "nome": contato_existente.get(
                            "nome",
                            nome
                        ),
                        "cpfCnpj": documento,
                        "criado_agora": False,
                        "resposta": contato_existente,
                        "recuperado_apos_duplicidade": True
                    }

        raise TinyAPIError(
            "Tiny recusou a criação do contato.",
            response.status_code,
            dados
        )

    contato_id = None

    if isinstance(dados, dict):
        contato_id = dados.get("id")

        if not contato_id and isinstance(dados.get("data"), dict):
            contato_id = dados["data"].get("id")

    if not contato_id:
        raise TinyAPIError(
            "Tiny criou o contato, mas não retornou o ID.",
            502,
            dados
        )

    return {
        "id": contato_id,
        "nome": nome,
        "cpfCnpj": documento,
        "criado_agora": True,
        "resposta": dados
    }

def obter_ou_criar_contato(dados_front):

    cliente = dados_front.get(
        "cliente",
        {}
    )

    documento = limpar_documento(
        cliente.get("cpf_cnpj")
    )

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado.",
            400
        )

    nome = (
        cliente.get("nome")
        or cliente.get("razao_social")
        or None
    )

    contato = localizar_contato(
        documento,
        nome,
        busca_exaustiva=True
    )

    if contato:

        contato_id = contato.get("id")

        if not contato_id:
            raise TinyAPIError(
                "Contato encontrado sem ID.",
                502,
                contato
            )

        print(
            "Contato encontrado no Tiny. ID:",
            contato_id
        )

        return {
            "id": contato_id,
            "criado_agora": False,
            "resposta": contato
        }

    print(
        "Contato não encontrado. Criando novo contato..."
    )

    return criar_contato(
        dados_front
    )

def localizar_produto_por_sku(
    sku
):

    if not sku:
        return None

    sku = str(sku).strip()

    if not sku:
        return None

    response = tiny_request(
        "GET",
        "/produtos",
        params={
            "codigo":
                sku,
            "limit":
                100,
            "offset":
                0
        }
    )

    dados = resposta_json(
        response
    )

    print(
        "Consulta produto SKU",
        sku,
        "HTTP",
        response.status_code
    )

    if not response.ok:
        raise TinyAPIError(
            "Erro ao consultar produto pelo SKU.",
            response.status_code,
            dados
        )

    produtos = dados.get(
        "itens",
        []
    )

    if not produtos:
        return None
    
    sku_normalizado = sku.casefold()

    for produto in produtos:
        sku_produto = produto.get(
            "sku"
        )

        if sku_produto is None:
            continue

        sku_produto_normalizado = str(
            sku_produto
        ).strip().casefold()

        if (
            sku_produto_normalizado
            and
            sku_produto_normalizado == sku_normalizado
        ):
            return produto

    return None

@app.route(
    "/api/testar-tiny",
    methods=["GET"]
)
def testar_tiny():

    try:

        response = tiny_request(

            "GET",

            "/contatos",

            params={

                "limit":
                    1,

                "offset":
                    0
            }
        )


        dados = resposta_json(
            response
        )


        if not response.ok:

            return jsonify({

                "erro":
                    "Token rejeitado pelo Tiny.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), response.status_code


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                "Autenticação com a API V3 funcionando.",

            "tiny":
                dados

        }), 200


    except TinyAPIError as e:

        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "detalhes":
                e.resposta

        }), e.status or 500

@app.route(
    "/api/gerar-proposta",
    methods=["POST"]
)
def gerar_proposta():

    try:

        dados_front = request.get_json(
            silent=True
        )


        if not dados_front:

            return jsonify({

                "erro":
                    "JSON inválido ou vazio."

            }), 400

        cliente = dados_front.get(
            "cliente",
            {}
        )


        cpf_cnpj = cliente.get(
            "cpf_cnpj"
        )


        if not cpf_cnpj:

            return jsonify({

                "erro":
                    "CPF/CNPJ do cliente não informado."

            }), 400


        contato = obter_ou_criar_contato(
            dados_front
        )


        contato_id = contato.get(
            "id"
        )


        if not contato_id:

            raise TinyAPIError(
                "Não foi possível obter o ID do contato.",
                502,
                contato
            )

        carrinho = dados_front.get(
            "carrinho",
            []
        )


        if not carrinho:

            return jsonify({

                "erro":
                    "Carrinho vazio."

            }), 400


        itens_tiny = []

        for indice, item in enumerate(
            carrinho,
            start=1
        ):

            sku = item.get(
                "sku"
            )

            if sku is not None:
                sku = str(sku).strip()

            if not sku:

                return jsonify({

                    "erro":
                        "Produto sem SKU.",

                    "item":
                        indice,

                    "produto":
                        item

                }), 400


            produto = localizar_produto_por_sku(
                sku
            )


            if not produto:

                return jsonify({

                    "erro":
                        "Produto não encontrado no Tiny pelo SKU.",

                    "item":
                        indice,

                    "sku":
                        sku,

                    "nome_site":
                        (
                            item.get(
                                "nome"
                            )
                            or
                            item.get(
                                "descricao"
                            )
                        )

                }), 404


            produto_id = produto.get(
                "id"
            )


            if not produto_id:

                return jsonify({

                    "erro":
                        "Produto encontrado sem ID no Tiny.",

                    "produto":
                        produto

                }), 502


            quantidade = float(
                item.get(
                    "quantidade",
                    1
                )
            )


            preco = float(
                item.get(
                    "preco_unitario",
                    0
                )
            )


            item_tiny = {

                "produto": {

                    "id":
                        produto_id
                },

                "quantidade":
                    quantidade,

                "valorUnitario":
                    preco
            }

            descricao = (

                item.get(
                    "descricao"
                )

                or

                item.get(
                    "nome"
                )
            )


            if descricao:

                item_tiny[
                    "descrComplementarOrc"
                ] = descricao


            itens_tiny.append(
                item_tiny
            )

        introducao_proposta = (
            dados_front.get("introducao")
            or
            "Prezado cliente, seguem abaixo proposta comercial com "
            "pagamento à vista com desconto e nossos dados bancários:\n\n"
            "Segue nossos dados bancários:\n"
            "BRFER Comércio de Ferramentas LTDA\n"
            "CNPJ 40.954.410/0001-96\n"
            "Banco: 341 – Itaú\n"
            "Agência: 8811\n"
            "Conta Corrente: 99874-2\n\n"
            "Se preferir, o pagamento pode ser realizado via PIX, a chave "
            "é o nosso CNPJ"
        )

        resumo_carrinho = dados_front.get(
            "resumo_carrinho",
            {}
        )

        def valor_float(nome):
            try:
                return float(resumo_carrinho.get(nome, 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        total_carrinho = valor_float("total")
        valor_avista = valor_float("avista")
        valor_parcela_3x = valor_float("parcela_3x")
        valor_parcela_12x = valor_float("parcela_12x")

        def dinheiro(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        data_proximo_contato = hoje + timedelta(days=3)

        data_proposta = hoje.isoformat()
        data_proximo_contato_str = data_proximo_contato.isoformat()

        outros_itens_servicos = (
            dados_front.get(
                "outros_itens_servicos"
            )
            or
            (
                "Condições de pagamento\n"
                f"Total: {dinheiro(total_carrinho)}\n"
                f"Pagamento à vista com desconto: {dinheiro(valor_avista)}\n"
                f"3x de {dinheiro(valor_parcela_3x)} sem juros\n"
                f"12x de {dinheiro(valor_parcela_12x)} com juros no cartão."
            )
        )

        hoje = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).date()

        data_proposta = hoje.isoformat()

        data_proximo_contato = (
            hoje + timedelta(days=3)
        ).isoformat()

        observacao_padrao = (
            dados_front.get(
                "observacoes"
            )
            or
            "Somos um E-COMMERCE, não reservamos estoque "
            "antes da aprovação do pagamento."
        )

        observacao_pagamento = (
            f"{observacao_padrao}\n\n"
            "Condições de pagamento do carrinho\n"
            f"Total do carrinho: {dinheiro(total_carrinho)}\n"
            f"Pagamento à vista com desconto: {dinheiro(valor_avista)}\n"
            f"3x de {dinheiro(valor_parcela_3x)} sem juros\n"
            f"12x de {dinheiro(valor_parcela_12x)} com juros no cartão."
        )

        payload_tiny = {

            "contato": {

                "id":
                    contato_id
            },

            "itens":
                itens_tiny,

            "introducao":
                introducao_proposta,

            "data":
                data_proposta,

            "dataProximoContato":
                data_proximo_contato,

            "outrosItensServicos":
                outros_itens_servicos,

            "observacao":
                observacao_pagamento,
        }


        print("")
        print(
            "========================================"
        )

        print(
            "CRIANDO PROPOSTA NO TINY"
        )

        print(
            json.dumps(
                payload_tiny,
                indent=2,
                ensure_ascii=False
            )
        )

        print(
            "========================================"
        )

        response_post = tiny_request(

            "POST",

            "/orcamentos",

            json=payload_tiny
        )


        dados_criacao = resposta_json(
            response_post
        )


        print(
            "POST /orcamentos:",
            response_post.status_code
        )


        if not response_post.ok:

            return jsonify({

                "erro":
                    "Tiny recusou a criação da proposta.",

                "status_tiny":
                    response_post.status_code,

                "resposta_tiny":
                    dados_criacao

            }), response_post.status_code

        orcamento_id = None

        if isinstance(
            dados_criacao,
            dict
        ):

            orcamento_id = (

                dados_criacao.get(
                    "id"
                )

                or

                dados_criacao.get(
                    "idOrcamento"
                )
            )


        if not orcamento_id:

            return jsonify({

                "erro":
                    (
                        "Tiny respondeu sucesso, "
                        "mas não retornou o ID da proposta."
                    ),

                "resposta_tiny":
                    dados_criacao

            }), 502

        response_get = tiny_request(

            "GET",

            f"/orcamentos/{orcamento_id}"
        )


        dados_orcamento = resposta_json(
            response_get
        )


        print(
            "GET /orcamentos/",
            orcamento_id,
            ":",
            response_get.status_code
        )


        if response_get.ok:

            # O PDF é produzido localmente pelo backend, usando os dados
            # efetivamente persistidos no Tiny e os dados do formulário.
            pdf_buffer = gerar_pdf_proposta(
                dados_front,
                dados_orcamento,
                contato,
                orcamento_id
            )

            resposta = send_file(
                pdf_buffer,
                mimetype="application/pdf",
                as_attachment=False,
                download_name=f"proposta_comercial{orcamento_id}.pdf"
            )

            # Força abertura inline no navegador em vez de download automático.
            resposta.headers["Content-Disposition"] = (
                f'inline; filename="proposta_comercial{orcamento_id}.pdf"'
            )
            resposta.headers["X-Proposta-Id"] = str(orcamento_id)

            return resposta

        return jsonify({

            "sucesso":
                True,

            "id":
                orcamento_id,

            "contato": {
                "id": contato_id,
                "criado_agora": contato.get("criado_agora", False)
            },

            "criacao":
                dados_criacao,

            "erro_get":
                True,

            "status_get_tiny":
                response_get.status_code,

            "resposta_get_tiny":
                dados_orcamento

        }), 200


    except TinyAPIError as e:

        print("")
        print(
            "========================================"
        )

        print(
            "ERRO TINY"
        )

        print(
            "MENSAGEM:",
            e.mensagem
        )

        print(
            "STATUS:",
            e.status
        )

        print(
            "RESPOSTA:",
            e.resposta
        )

        print(
            "========================================"
        )


        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "resposta_tiny":
                e.resposta

        }), e.status or 502


    except requests.RequestException as e:

        return jsonify({

            "erro":
                "Erro de comunicação com o Tiny.",

            "detalhes":
                str(e)

        }), 502


    except Exception as e:

        print(
            "ERRO INTERNO:",
            str(e)
        )


        return jsonify({

            "erro":
                "Erro interno no servidor.",

            "detalhes":
                str(e)

        }), 500

@app.route(
    "/api/obter-proposta/<int:id_proposta>",
    methods=["GET"]
)
def obter_proposta(
    id_proposta
):

    try:

        response = tiny_request(

            "GET",

            f"/orcamentos/{id_proposta}"
        )


        dados = resposta_json(
            response
        )


        if not response.ok:

            return jsonify({

                "erro":
                    "Falha ao obter o orçamento.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), response.status_code


        return jsonify(
            dados
        ), 200


    except TinyAPIError as e:

        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "resposta_tiny":
                e.resposta

        }), e.status or 502


    except Exception as e:

        return jsonify({

            "erro":
                "Erro interno.",

            "detalhes":
                str(e)

        }), 500


@app.route(
    "/api/status",
    methods=["GET"]
)
def status():

    try:

        tokens = carregar_tokens()


        if not tokens:

            return jsonify({

                "autorizado":
                    False,

                "mensagem":
                    "Aplicação ainda não autorizada.",

                "autorizar":
                    "/api/oauth/autorizar"

            }), 200


        expires_at = int(
            tokens.get(
                "expires_at",
                0
            )
        )


        agora = int(
            time.time()
        )


        return jsonify({

            "autorizado":
                True,

            "access_token_valido":
                agora < expires_at,

            "tokens_armazenados":
                True,

            "mensagem":
                "Credenciais OAuth encontradas no Redis."

        }), 200


    except Exception as e:

        return jsonify({

            "erro":
                str(e)

        }), 500


@app.route(
    "/api/oauth/revogar",
    methods=["POST"]
)
def revogar_oauth():

    try:

        redis_delete(
            TINY_TOKEN_KEY
        )


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                "Tokens removidos do Upstash Redis."

        }), 200


    except Exception as e:

        return jsonify({

            "erro":
                "Não foi possível remover os tokens.",

            "detalhes":
                str(e)

        }), 500

@app.route(
    "/",
    methods=["GET"]
)
def index():

    return jsonify({

        "status":
            "online",

        "servico":
            "Gerador de Propostas Comerciais",

        "api":
            "Olist ERP API V3",

        "endpoints": {

            "autorizar":
                "/api/oauth/autorizar",

            "callback":
                "/api/oauth/callback",

            "status":
                "/api/status",

            "testar":
                "/api/testar-tiny",

            "gerar":
                "/api/gerar-proposta",

            "obter":
                "/api/obter-proposta/<id>",

            "revogar":
                "/api/oauth/revogar"
        }

    }), 200

@app.route(
    "/api/imprimir-proposta/<int:id_proposta>",
    methods=["POST"]
)
def imprimir_proposta(id_proposta):
    try:
        response = tiny_request(
            "POST",
            f"/orcamentos/{id_proposta}/imprimir"
        )
        
        dados = resposta_json(response)
        
        print(f"POST /orcamentos/{id_proposta}/imprimir:", response.status_code)

        if not response.ok:
            return jsonify({
                "erro": "Falha ao gerar o PDF da proposta.",
                "status_tiny": response.status_code,
                "resposta_tiny": dados
            }), response.status_code

        return jsonify(dados), 200

    except TinyAPIError as e:
        return jsonify({
            "erro": e.mensagem,
            "status_tiny": e.status,
            "resposta_tiny": e.resposta
        }), e.status or 502

    except Exception as e:
        return jsonify({
            "erro": "Erro interno ao tentar imprimir.",
            "detalhes": str(e)
        }), 500