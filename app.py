from flask import Flask, render_template, request, jsonify, send_file
import boto3
import os
from dotenv import load_dotenv
from pathlib import Path
import re
from datetime import datetime
import json

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'

# Create necessary folders
Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
Path(app.config['OUTPUT_FOLDER']).mkdir(exist_ok=True)

class PodcastGenerator:
    def __init__(self):
        self.polly_client = boto3.client(
            'polly',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.ssml_wrapper = '<speak>{}</speak>'
    
    def get_available_voices(self):
        """Get all available voices grouped by language"""
        try:
            response = self.polly_client.describe_voices()
            voices = {}
            
            for voice in response['Voices']:
                lang = voice['LanguageCode']
                if lang not in voices:
                    voices[lang] = []
                
                voices[lang].append({
                    'id': voice['Id'],
                    'name': voice['Name'],
                    'gender': voice['Gender'],
                    'language': voice['LanguageName'],
                    'languageCode': voice['LanguageCode'],
                    'engines': voice.get('SupportedEngines', [])
                })
            
            return voices
        except Exception as e:
            print(f"Error fetching voices: {e}")
            return {}
    
    def add_ssml_pauses(self, text):
        """Add natural pauses using SSML"""
        text = re.sub(r'([.!?])\s+', r'\1<break time="500ms"/> ', text)
        text = re.sub(r'(,)\s+', r'\1<break time="300ms"/> ', text)
        return text
    
    def create_ssml_with_prosody(self, text, rate='medium', pitch='medium'):
        """Create SSML with prosody controls"""
        text = self.add_ssml_pauses(text)
        prosody_text = f'<prosody rate="{rate}" pitch="{pitch}">{text}</prosody>'
        return self.ssml_wrapper.format(prosody_text)
    
    def generate_audio(self, text, voice_id='Joanna', engine='neural', 
                      use_ssml=False, rate='medium', pitch='medium'):
        """Generate audio and return file path"""
        try:
            # Create unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"podcast_{voice_id}_{timestamp}.mp3"
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            
            if use_ssml:
                ssml_text = self.create_ssml_with_prosody(text, rate, pitch)
                response = self.polly_client.synthesize_speech(
                    Text=ssml_text,
                    TextType='ssml',
                    OutputFormat='mp3',
                    VoiceId=voice_id,
                    Engine=engine
                )
            else:
                response = self.polly_client.synthesize_speech(
                    Text=text,
                    OutputFormat='mp3',
                    VoiceId=voice_id,
                    Engine=engine
                )
            
            # Save audio file
            with open(output_path, 'wb') as f:
                f.write(response['AudioStream'].read())
            
            file_size = os.path.getsize(output_path)
            
            return {
                'success': True,
                'filename': filename,
                'path': output_path,
                'size': file_size
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

# Initialize generator
generator = PodcastGenerator()

@app.route('/')
def index():
    """Render main page"""
    return render_template('index.html')

@app.route('/api/voices')
def get_voices():
    """API endpoint to get available voices"""
    voices = generator.get_available_voices()
    return jsonify(voices)

@app.route('/api/generate', methods=['POST'])
def generate_podcast():
    """API endpoint to generate podcast"""
    try:
        data = request.json
        
        text = data.get('text', '').strip()
        voice_id = data.get('voice', 'Joanna')
        engine = data.get('engine', 'neural')
        use_ssml = data.get('useSSML', False)
        rate = data.get('rate', 'medium')
        pitch = data.get('pitch', 'medium')
        
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400
        
        # Check character limit
        max_chars = 3000 if engine == 'neural' else 6000
        if len(text) > max_chars:
            return jsonify({
                'success': False, 
                'error': f'Text too long. Maximum {max_chars} characters for {engine} engine.'
            }), 400
        
        # Generate audio
        result = generator.generate_audio(text, voice_id, engine, use_ssml, rate, pitch)
        
        if result['success']:
            return jsonify({
                'success': True,
                'filename': result['filename'],
                'size': result['size'],
                'downloadUrl': f"/download/{result['filename']}"
            })
        else:
            return jsonify({'success': False, 'error': result['error']}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """API endpoint to upload text file"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400
        
        # Read file content
        content = file.read().decode('utf-8')
        
        return jsonify({
            'success': True,
            'text': content,
            'length': len(content)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download generated audio file"""
    try:
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)