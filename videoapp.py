import numpy as np
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
import tempfile
import streamlit as st
import os
import requests
import json
from openai import OpenAI
import time
from PIL import Image, ImageDraw, ImageFont

# Secrets from Streamlit Cloud
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
TYPECAST_API_KEY = st.secrets["TYPECAST_API_KEY"]

# GitHub URL로부터 파일 다운로드
def download_file(url, output_path):
    response = requests.get(url)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        f.write(response.content)

# 영상 파일 다운로드 및 임시 파일로 저장
def get_video_path(github_url):
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
    download_file(github_url, temp_file.name)
    return temp_file.name

# GitHub에 업로드된 영상 파일의 URL
INTRO_VIDEO_URL = "https://github.com/DECK6/cheervideo/raw/main/intro.mp4"
OUTRO_VIDEO_URL = "https://github.com/DECK6/cheervideo/raw/main/outro.mp4"

# 영상 파일 경로 설정
INTRO_VIDEO_PATH = get_video_path(INTRO_VIDEO_URL)
OUTRO_VIDEO_PATH = get_video_path(OUTRO_VIDEO_URL)

# 나머지 코드

def download_font(url, font_path):
    response = requests.get(url)
    with open(font_path, 'wb') as f:
        f.write(response.content)

def add_text_with_image(video_path, text, output_path, font_path):
    video = VideoFileClip(video_path)
    font_size = 90
    color = '#002470'  # 텍스트 색상을 HEX 코드로 설정
    text_img = create_text_image(text, font_path, font_size, color, video.w, video.h)
    
    # 텍스트 이미지 클립 생성 및 위치 설정
    text_clip = ImageClip(text_img).set_duration(5).set_position(('center', 'center'))

    video_with_text = CompositeVideoClip([video, text_clip])
    video_with_text.write_videofile(output_path, codec='libx264', audio_codec='aac')

def create_text_image(text, font_path, font_size, color, img_width, img_height):
    # 텍스트 이미지를 생성하는 함수
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype(font_path, font_size)
    
    lines = text.split('!')
    line1 = lines[0] + '!'
    line2 = lines[1] + '!' if len(lines) > 1 else ""

    w1, h1 = draw.textbbox((0, 0), line1, font=font)[2:]
    w2, h2 = draw.textbbox((0, 0), line2, font=font)[2:]
    
    y1 = int(img_height * 0.655)  # 텍스트의 y 위치 (비디오 높이의 80% 지점)
    y2 = y1 + h1 + 10  # 두 번째 줄 텍스트의 y 위치

    x1 = (img_width - w1) // 2 + 100  # 100픽셀 오른쪽으로 이동
    x2 = (img_width - w2) // 2 + 100

    draw.text((x1, y1), line1, font=font, fill=color)
    draw.text((x2, y2), line2, font=font, fill=color)
    
    return np.array(img)

def add_audio_to_video(video_path, audio_path, output_path):
    video = VideoFileClip(video_path)
    new_audio = AudioFileClip(audio_path).set_start(1.333)
    
    original_audio = video.audio
    final_audio = CompositeAudioClip([original_audio, new_audio])
    
    final_video = video.set_audio(final_audio)
    
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
        
        add_text_with_image(intro_video_path, text, temp_video_with_text_path, font_path)
        add_audio_to_video(temp_video_with_text_path, audio_file, temp_final_video_path)
        
        return temp_final_video_path
        
    except Exception as e:
        st.error(f"Error in process_video: {str(e)}")
        st.error(f"intro_video_path: {intro_video_path}")
        st.error(f"audio_file: {audio_file}")
        st.error(f"temp_video_with_text_path: {temp_video_with_text_path}")
        raise
    finally:
        if 'temp_video_with_text_path' in locals() and os.path.exists(temp_video_with_text_path):
            os.unlink(temp_video_with_text_path)

def combine_videos(intro_video, outro_video):
    intro_clip = VideoFileClip(intro_video)
    outro_clip = VideoFileClip(outro_video)
    
    final_clip = concatenate_videoclips([intro_clip, outro_clip])

    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_final_video:
        temp_final_video_path = temp_final_video.name
    
    final_clip.write_videofile(temp_final_video_path, codec='libx264', audio_codec='aac')
    
    intro_clip.close()
    outro_clip.close()
    final_clip.close()
    
    return temp_final_video_path

def process_with_llm(group_name, name):
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    completion = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "입력된 단체명(최대 8자)과 이름(최대 5자)을 받아 '{단체명}! {이름}이 응원해!' 또는 '{단체명}! {이름}가 응원해!' 형식으로 반환하세요. 이름이 받침으로 끝나면 '이', 그렇지 않으면 '가'를 사용니다. 단체명과 이름은 절대로 변경, 가공 할 수  없습니다. 그 외 어떠한 설명도 추가하지 않습니다."},
            {"role": "user", "content": f"단체명: {group_name}, 이름: {name}"}
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
        'Authorization': f'Bearer {st.secrets["TYPECAST_API_KEY"]}'
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

# Streamlit 앱 설정
st.set_page_config(page_title="응원 메시지 생성기", page_icon="🎥")
st.title("응원 메시지 생성기")

# 사용자 입력
group_name = st.text_input("단체명 (최대 8자):", max_chars=8)
name = st.text_input("이름 (최대 5자):", max_chars=5)

# 폰트 다운로드
font_url = "https://github.com/orioncactus/pretendard/blob/main/packages/pretendard/dist/public/static/Pretendard-Bold.otf?raw=true"
font_path = "Pretendard-Bold.otf"
download_font(font_url, font_path)

# 처리 버튼
if st.button("메시지 생성"):
    if group_name and name:
        with st.spinner("동영상 생성 중..."):
            processed_text = process_with_llm(group_name, name)
            st.write(f"생성된 메시지: {processed_text}")

            audio_file = generate_audio(processed_text)

            intro_video = process_video(processed_text, audio_file, INTRO_VIDEO_PATH, font_path)

            final_video = combine_videos(intro_video, OUTRO_VIDEO_PATH)

            st.video(final_video)

            os.unlink(audio_file)
            os.unlink(intro_video)
            os.unlink(final_video)
    else:
        st.error("단체명과 이름을 모두 입력해주세요.")

st.info("이 앱은 입력받은 단체명과 이름으로 응원 메시지를 생성하고, 이를 미리 준비된 인트로 영상에 삽입한 후 아웃트로 영상과 합쳐 최종 영상을 생성합니다.")
