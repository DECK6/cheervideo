import numpy as np
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, AudioClip
from moviepy.audio.AudioClip import CompositeAudioClip
import tempfile
import streamlit as st
import os
import requests
import json
from openai import OpenAI
import time
from PIL import Image, ImageDraw, ImageFont
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import datetime

# Constants and settings
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
TYPECAST_API_KEY = st.secrets["TYPECAST_API_KEY"]
INTRO_VIDEO_URL = "https://github.com/DECK6/cheervideo/raw/main/intro.mp4"
OUTRO_VIDEO_URL = "https://github.com/DECK6/cheervideo/raw/main/outro.mp4"
FONT_URL = "https://github.com/DECK6/cheervideo/raw/main/Giants-Inline.otf"
HEADER_URL = "https://github.com/DECK6/gamechar/raw/main/header.png"
EMAIL_SETTINGS = {
    "SMTP_SERVER": "smtp.gmail.com",
    "SMTP_PORT": 587,
    "SENDER_EMAIL": "dnmdaia@gmail.com",
    "SENDER_PASSWORD": "iudy dgqr fuin lukc"
}

# Helper functions
def download_file(url, output_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(response.content)

def get_video_path(github_url):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    download_file(github_url, temp_file.name)
    return temp_file.name

INTRO_VIDEO_PATH = get_video_path(INTRO_VIDEO_URL)
OUTRO_VIDEO_PATH = get_video_path(OUTRO_VIDEO_URL)

def download_font(url, font_path):
    download_file(url, font_path)

def create_text_image(text, font_path, font_size, color, img_width, img_height):
    try:
        img_width = int(img_width)
        img_height = int(img_height)
    except ValueError:
        raise ValueError(f"Invalid image dimensions: width={img_width}, height={img_height}. Must be integers.")
    
    if img_width <= 0 or img_height <= 0:
        raise ValueError(f"Invalid image dimensions: width={img_width}, height={img_height}. Must be positive integers.")
    
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    
    # Split text at the first exclamation mark
    parts = text.split('!', 1)
    line1 = parts[0] + '!'
    line2 = parts[1] + '!' if len(parts) > 1 else ""
    
    # Calculate text dimensions
    w1, h1 = draw.textbbox((0, 0), line1, font=font)[2:]
    w2, h2 = draw.textbbox((0, 0), line2, font=font)[2:]
    
    # Calculate positions
    y1 = int(img_height * 0.725)  # 80% of the screen height
    y2 = y1 + h1 + 1  # 10 pixels between lines
    x1 = (img_width - w1) // 2 + 100  # 100 pixels to the right
    x2 = (img_width - w2) // 2 + 100
    
    # Draw text
    draw.text((x1, y1), line1, font=font, fill=color)
    draw.text((x2, y2), line2, font=font, fill=color)
    
    return np.array(img)



def process_full_video(intro_video_path, outro_video_path, display_text, font_path, audio_file):
    # 비디오 클립 로드
    intro_clip = VideoFileClip(intro_video_path)
    outro_clip = VideoFileClip(outro_video_path)
    
    # 오디오 클립 로드
    audio_clip = AudioFileClip(audio_file).set_start(1.0)
    
    # 인트로 길이 계산
    intro_duration = intro_clip.duration
    
    # 오디오 길이 계산
    audio_duration = audio_clip.duration
    
    # 앞부분 1초 무음, 뒷부분 무음 길이 계산
    remaining_silence_duration = intro_duration - (1.0 + audio_duration)
    
    if remaining_silence_duration < 0:
        raise ValueError("The audio duration exceeds the intro video duration minus 1 second for the delay.")
    
    # 무음 오디오 클립 생성
    silence_start = AudioClip(lambda t: 0, duration=1.0, fps=44100)
    silence_end = AudioClip(lambda t: 0, duration=remaining_silence_duration, fps=44100)
    
    # 무음과 오디오 클립 결합
    combined_audio = CompositeAudioClip([silence_start, audio_clip, silence_end])
    
    # 인트로 클립에 결합된 오디오 추가
    intro_with_audio = intro_clip.set_audio(combined_audio)
    
    # 인트로와 아웃트로 클립 연결
    final_clip = concatenate_videoclips([intro_with_audio, outro_clip])
    
    # 전체 비디오에 텍스트 추가
    font_size = 100
    color = '#503F95'  # Purple color
    text_img = create_text_image(display_text, font_path, font_size, color, final_clip.w, final_clip.h)
    text_clip = ImageClip(text_img).set_duration(final_clip.duration)
    
    video_with_text = CompositeVideoClip([final_clip, text_clip])
    
    # 임시 파일 생성 및 비디오 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_final_video:
        temp_final_video_path = temp_final_video.name
    
    video_with_text.write_videofile(temp_final_video_path, codec='libx264', audio_codec='aac')
    
    # 클립 닫기
    intro_clip.close()
    outro_clip.close()
    audio_clip.close()
    final_clip.close()
    video_with_text.close()
    
    return temp_final_video_path



def process_with_llm_for_display(group_name, name):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        messages=[
            {"role": "system", "content": "입력된 단체명(최대 10자)과 이름(최대 5자)을 받아 '{단체명}! {이름}이 응원해!' 또는 '{단체명}! {이름}가 응원해!' 형식으로 반환하세요. 이름이 받침으로 끝나면 '이', 그렇지 않으면 '가'를 사용합니다. 단체명과 이름은 절대로 변경, 가공 할 수 없습니다. 그 외 어떠한 설명도 추가하지 않습니다."},
            {"role": "user", "content": f"단체명: {group_name}, 이름: {name}"}
        ]
    )
    return completion.choices[0].message.content

def process_with_llm_for_audio(group_name, name, cheer_content):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": """응원 메세지는 입력된 단체명, 이름, 응원내용을 받아  "{이름}이/가 {단체명}을 응원해!  {응원문구}! "로 응원한다는 형식으로 응원한다는 메세지를 반환하세요. 이름이 받침으로 끝나면 '이', 그렇지 않으면 '가'를 사용합니다. {응원문구} 내용은 {응원내용}을 기반으로 기반으로 15자에서 20자 정도의 메세지를 생성하고 자연스러운 내용으로 이어가며 '화이팅!'등의 구호로 끝맺음 합니다. 어떠한 내용을 입력 받더라도 원본 메세지의 관련성은 유지하면서 욕설과 비속어, 부정적 내용은 제거하고 자연스러운 응원메세지를 만들며 밝고 긍정적인 응원 내용을 만듭니다. 아이같은 말투로 출력합니다. '~~한다'같은 말투는 사용하지 않고 '~~해'를 사용합니다. 게임대회 응원 메세지라는 점을 고려합니다. 이모티콘, 이모지는 사용하지 않습니다. {이름}과 {단체명}은 유지하면서 연결성을 고려해 문장은 최대한 자연스럽게 다듬어야 합니다."""},
            {"role": "user", "content": f"단체명: {group_name}, 이름: {name}, 응원내용: {cheer_content}"}
        ]
    )
    return completion.choices[0].message.content

def generate_audio(text):
    url = "https://typecast.ai/api/speak"
    payload = json.dumps({
        "actor_id": "66596206b7bd6e89c3a2c54e",
        "text": text,
        "lang": "auto",
        "tempo": 1.3,
        "volume": 100,
        "pitch": 0,
        "xapi_hd": True,
        "max_seconds": 60,
        "model_version": "latest",
        "xapi_audio_format": "wav"
    })
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {TYPECAST_API_KEY}'
    }
    
    response = requests.post(url, headers=headers, data=payload)
    
    if response.status_code != 200:
        st.error(f"TTS API Error: Status code {response.status_code}")
        st.json(response.json())
        raise Exception("Failed to initiate audio generation")

    response_data = response.json()
    if 'result' not in response_data or 'speak_v2_url' not in response_data['result']:
        st.error("Unexpected API response structure")
        st.json(response_data)
        raise Exception("Unexpected API response structure")

    speak_v2_url = response_data['result']['speak_v2_url']
    
    for _ in range(120):
        status_response = requests.get(speak_v2_url, headers=headers)
        status_data = status_response.json()
        
        if status_data['result']['status'] == 'done':
            audio_download_url = status_data['result']['audio_download_url']
            break
        elif status_data['result']['status'] == 'progress':
            time.sleep(1)
            continue
        else:
            st.error(f"Unexpected status: {status_data['result']['status']}")
            raise Exception("Unexpected audio generation status")
    else:
        st.error("Audio generation timed out")
        raise Exception("Audio generation timed out")
    
    audio_response = requests.get(audio_download_url)
    if audio_response.status_code == 200:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            temp_audio.write(audio_response.content)
            return temp_audio.name
    else:
        st.error(f"Failed to download audio file: Status code {audio_response.status_code}")
        raise Exception("Failed to download audio file")

def send_email(receiver_email, video_path, group_name, name, cheer_content, display_text, audio_text):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SETTINGS["SENDER_EMAIL"]
    msg['To'] = receiver_email
    msg['Subject'] = "2024 Youth E-Sports Festival 응원영상"

    body = f"""제작한 응원 영상이 도착했습니다.

단체명: {group_name}
이름: {name}
응원내용: {cheer_content}

화면 메시지:
{display_text}

음성 메시지:
{audio_text}
"""
    msg.attach(MIMEText(body, 'plain'))

    with open(video_path, "rb") as file:
        part = MIMEApplication(file.read(), Name="cheer_video.mp4")
    part['Content-Disposition'] = f'attachment; filename="cheer_video.mp4"'
    msg.attach(part)

    try:
        server = smtplib.SMTP(EMAIL_SETTINGS["SMTP_SERVER"], EMAIL_SETTINGS["SMTP_PORT"])
        server.starttls()
        server.login(EMAIL_SETTINGS["SENDER_EMAIL"], EMAIL_SETTINGS["SENDER_PASSWORD"])
        server.send_message(msg)
        server.quit()
        st.success("이메일이 전송되었습니다.")
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")

def upload_video_to_drive(video_path):
    # 인증 정보 로드
    creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/drive'])

    # Drive API 클라이언트 생성
    service = build('drive', 'v3', credentials=creds)

    # 'video_upload' 폴더 ID 찾기 또는 생성
    folder_name = 'video_upload'
    folder_id = find_or_create_folder(service, folder_name)

    # 파일 이름에 타임스탬프 추가
    file_name = os.path.basename(video_path)
    name, extension = os.path.splitext(file_name)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_file_name = f"{name}_{timestamp}{extension}"

    file_metadata = {
        'name': new_file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(video_path, resumable=True)
    
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields='id,webViewLink').execute()
        file_id = file.get('id')
        share_link = file.get('webViewLink')

        # 파일을 공개로 설정 (선택사항)
        service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            fields='id'
        ).execute()

        st.success(f"Video uploaded to Google Drive successfully. Share link: {share_link}")
        return file_id, share_link
    except Exception as e:
        st.error(f"An error occurred while uploading to Google Drive: {str(e)}")
        return None, None

def find_or_create_folder(service, folder_name):
    # 폴더 검색
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields='files(id, name)'
    ).execute()
    folders = results.get('files', [])

    # 폴더가 존재하면 해당 ID 반환
    if folders:
        return folders[0]['id']
    
    # 폴더가 없으면 새로 생성
    folder_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=folder_metadata, fields='id').execute()
    return folder.get('id')
    
# Streamlit app
st.set_page_config(page_title="응원 메시지 생성기", page_icon="🎥", layout="wide")

# Header
st.image(HEADER_URL)

# Two-column layout
col1, col2 = st.columns(2)

with col1:
    st.title("🎉🎉 Cheer up! 우리 팀을 응원합니다! 🎉🎉\n💪🔥 우리 센터 대표팀을 향한 힘찬 응원 영상 보내기 📹💥")
    group_name = st.text_input("응원하고 싶은 친구 이름 또는 단체명 (최대 10자):", max_chars=10)
    name = st.text_input("내 이름 (최대 5자):", max_chars=5)
    cheer_content = st.text_input("응원 멘트 (최대 10자):", max_chars=10)
    email = st.text_input("이메일 주소:")
    st.write("CHAT GPT가 응원 멘트를 멋지게 다듬어 볼게요!")

    # Font download
    font_path = "Giants-Inline.otf"
    download_font(FONT_URL, font_path)

if st.button("메시지 생성"):
    if group_name and name and cheer_content:  # 이메일 필수 조건 제거
        with st.spinner("동영상 생성 중..."):
            display_text = process_with_llm_for_display(group_name, name)
            audio_text = process_with_llm_for_audio(group_name, name, cheer_content)
        
            st.write(f"화면 메시지: {display_text}")
            st.write(f"음성 메시지: {audio_text}")

            audio_file = generate_audio(audio_text)

            # 전체 비디오 처리 (인트로 + 아웃트로 + 텍스트 + 오디오)
            final_video = process_full_video(INTRO_VIDEO_PATH, OUTRO_VIDEO_PATH, display_text, font_path, audio_file)

            # Google Drive에 업로드
            file_id, share_link = upload_video_to_drive(final_video)

            if file_id:
                st.write(f"Video uploaded to Google Drive. Share link: {share_link}")

            if email:  # 이메일이 있을 때만 전송
                send_email(email, final_video, group_name, name, cheer_content, display_text, audio_text)
                st.success("이메일이 전송되었습니다.")
            else:
                st.warning("이메일 주소가 입력되지 않아 영상이 이메일로 발송되지 않았습니다.")
            
            with col2:
                st.video(final_video)

            os.unlink(audio_file)
            os.unlink(final_video)
    else:
        st.error("모든 필드를 입력해주세요.")



