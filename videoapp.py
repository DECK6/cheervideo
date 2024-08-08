import numpy as np
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip, AudioClip
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
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    
    lines = text.split('\n')
    total_height = sum([draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines])
    y = img_height - total_height - 50  # 50 pixels from bottom
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (img_width - w) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += h + 10  # 10 pixels between lines
    
    return np.array(img)

def add_text_to_video(video_path, text, output_path, font_path):
    video = VideoFileClip(video_path)
    font_size = 70
    color = '#503F95'  # White color
    text_img = create_text_image(text, font_path, font_size, color, video.w, video.h)
    text_clip = ImageClip(text_img).set_duration(video.duration)
    video_with_text = CompositeVideoClip([video, text_clip])
    video_with_text.write_videofile(output_path, codec='libx264', audio_codec='aac')

def add_audio_to_video(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    new_audio = AudioFileClip(audio_path)
    
    # 인트로 영상의 1초부터 오디오 시작
    new_audio = new_audio.set_start(1.0)
    
    # 비디오 길이에 맞춰 오디오 조정
    new_audio = new_audio.set_duration(video.duration - 1.0)
    
    # 새 오디오를 비디오에 설정 (기존 오디오 대체)
    final_video = video.set_audio(new_audio)
    
    final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
    video.close()
    new_audio.close()
    final_video.close()

def process_video(text, audio_file, intro_video_path, font_path):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_video_with_text:
            temp_video_with_text_path = temp_video_with_text.name
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_final_video:
            temp_final_video_path = temp_final_video.name
        add_text_to_video(intro_video_path, text, temp_video_with_text_path, font_path)
        add_audio_to_video(temp_video_with_text_path, audio_file, temp_final_video_path)
        return temp_final_video_path
    except Exception as e:
        st.error(f"Error in process_video: {str(e)}")
        raise
    finally:
        if 'temp_video_with_text_path' in locals() and os.path.exists(temp_video_with_text_path):
            os.unlink(temp_video_with_text_path)

def combine_videos(intro_video, outro_video, text, font_path):
    intro_clip = VideoFileClip(intro_video)
    outro_clip = VideoFileClip(outro_video)
    
    intro_with_text = add_text_to_clip(intro_clip, text, font_path)
    outro_with_text = add_text_to_clip(outro_clip, text, font_path)
    
    final_clip = concatenate_videoclips([intro_with_text, outro_with_text])
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_final_video:
        temp_final_video_path = temp_final_video.name
    
    final_clip.write_videofile(temp_final_video_path, codec='libx264', audio_codec='aac')
    
    intro_clip.close()
    outro_clip.close()
    final_clip.close()
    
    return temp_final_video_path

def add_text_to_clip(clip, text, font_path):
    font_size = 70
    color = '#503F95'  # White color
    text_img = create_text_image(text, font_path, font_size, clip.w, clip.h)
    text_clip = ImageClip(text_img).set_duration(clip.duration)
    return CompositeVideoClip([clip, text_clip])

def process_with_llm_for_display(group_name, name):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "입력된 단체명(최대 10자)과 이름(최대 5자)을 받아 '{단체명}! {이름}이 응원해!' 또는 '{단체명}! {이름}가 응원해!' 형식으로 반환하세요. 이름이 받침으로 끝나면 '이', 그렇지 않으면 '가'를 사용합니다. 단체명과 이름은 절대로 변경, 가공 할 수 없습니다. 그 외 어떠한 설명도 추가하지 않습니다."},
            {"role": "user", "content": f"단체명: {group_name}, 이름: {name}"}
        ]
    )
    return completion.choices[0].message.content

def process_with_llm_for_audio(group_name, name, cheer_content):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "입력된 단체명(최대 10자), 이름(최대 5자), 응원내용(최대 15자)을 받아 '{이름}이/가 {단체명} {응원내용}'의 형식으로 응원한다는 메세지를 반환하세요. 이름이 받침으로 끝나면 '이', 그렇지 않으면 '가'를 사용합니다. 응원 내용은 최대 15자로 어떠한 내용을 입력 받더라도 메세지의 관련성은 유지하되 욕설과 비속어 없는 밝고 긍정적인 응원 내용으로 변환하여 출력합니다. 게임대회 응원 메세지라는 점을 고려합니다."},
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

def send_email(receiver_email, video_path):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SETTINGS["SENDER_EMAIL"]
    msg['To'] = receiver_email
    msg['Subject'] = "Your Cheer Video"

    body = "Here's your cheer video!"
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
        st.success("Email sent successfully!")
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")

# Streamlit app
st.set_page_config(page_title="응원 메시지 생성기", page_icon="🎥", layout="wide")

# Header
st.image(HEADER_URL)

# Two-column layout
col1, col2 = st.columns(2)

with col1:
    st.title("응원 메시지 생성기")
    group_name = st.text_input("단체명 (최대 10자):", max_chars=10)
    name = st.text_input("이름 (최대 5자):", max_chars=5)
    cheer_content = st.text_input("응원 내용 (최대 10자):", max_chars=10)
    email = st.text_input("이메일 주소:")

    # Font download
    font_path = "Giants-Inline.otf"
    download_font(FONT_URL, font_path)

    if st.button("메시지 생성"):
        if group_name and name and cheer_content and email:
            with st.spinner("동영상 생성 중..."):
                display_text = process_with_llm_for_display(group_name, name)
                audio_text = process_with_llm_for_audio(group_name, name, cheer_content)
            
                st.write(f"화면에 표시될 메시지: {display_text}")
                st.write(f"음성으로 생성될 메시지: {audio_text}")

                audio_file = generate_audio(audio_text)

                intro_video = process_video(display_text, audio_file, INTRO_VIDEO_PATH, font_path)

                final_video = combine_videos(intro_video, OUTRO_VIDEO_PATH, display_text, font_path)

                send_email(email, final_video)

                with col2:
                    st.video(final_video)

                os.unlink(audio_file)
                os.unlink(intro_video)
                os.unlink(final_video)
        else:
            st.error("모든 필드를 입력해주세요.")

        st.info("이 앱은 입력받은 단체명과 이름으로 응원 메시지를 생성하고, 이를 미리 준비된 인트로 영상에 삽입한 후 아웃트로 영상과 합쳐 최종 영상을 생성합니다.")
