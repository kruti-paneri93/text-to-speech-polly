import boto3
import os
from dotenv import load_dotenv
from pathlib import Path
import re

load_dotenv()

class PodcastCLI:
    def __init__(self):
        self.polly_client = boto3.client(
            'polly',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.voices = self.load_voices()
    
    def load_voices(self):
        """Load available voices grouped by language"""
        try:
            response = self.polly_client.describe_voices()
            voices = {}
            
            for voice in response['Voices']:
                lang = voice['LanguageCode']
                if lang not in voices:
                    voices[lang] = []
                voices[lang].append(voice)
            
            return voices
        except Exception as e:
            print(f"Error loading voices: {e}")
            return {}
    
    def display_menu(self):
        """Display main menu"""
        print("\n" + "=" * 60)
        print("  📻 TEXT-TO-SPEECH PODCAST GENERATOR")
        print("=" * 60)
        print("\n1. Convert text from keyboard input")
        print("2. Convert text from file")
        print("3. List available voices")
        print("4. Generate sample with different voices")
        print("5. Advanced: Use SSML features")
        print("6. Exit")
        print("\n" + "-" * 60)
    
    def list_voices_menu(self):
        """Interactive voice listing"""
        print("\n📋 Available Languages:")
        langs = list(self.voices.keys())
        for i, lang in enumerate(langs, 1):
            count = len(self.voices[lang])
            print(f"{i}. {lang} ({count} voices)")
        
        try:
            choice = int(input("\nSelect language (number): "))
            if 1 <= choice <= len(langs):
                selected_lang = langs[choice - 1]
                print(f"\n🎙️  Voices for {selected_lang}:")
                for i, voice in enumerate(self.voices[selected_lang], 1):
                    engine = "Neural ⚡" if "neural" in voice.get('SupportedEngines', []) else "Standard"
                    print(f"{i}. {voice['Name']:15} | {voice['Gender']:7} | {engine}")
            else:
                print("Invalid choice!")
        except ValueError:
            print("Please enter a number!")
    
    def text_input_mode(self):
        """Convert text entered by user"""
        print("\n✍️  Enter your text (type 'END' on a new line when done):")
        lines = []
        while True:
            line = input()
            if line.strip().upper() == 'END':
                break
            lines.append(line)
        
        text = ' '.join(lines)
        
        if not text.strip():
            print("No text entered!")
            return
        
        # Select voice
        voice = self.select_voice()
        if not voice:
            return
        
        # Select engine
        engine = self.select_engine(voice)
        
        # Generate output filename
        output_file = input("\nOutput filename (default: output/podcast.mp3): ").strip()
        if not output_file:
            output_file = "output/podcast.mp3"
        
        if not output_file.endswith('.mp3'):
            output_file += '.mp3'
        
        # Generate audio
        self.generate_audio(text, output_file, voice['Name'], engine)
    
    def file_input_mode(self):
        """Convert text from file"""
        filepath = input("\n📄 Enter file path: ").strip()
        
        if not os.path.exists(filepath):
            print(f"File not found: {filepath}")
            return
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
            
            print(f"✓ Loaded {len(text)} characters from {filepath}")
            
            # Select voice
            voice = self.select_voice()
            if not voice:
                return
            
            # Select engine
            engine = self.select_engine(voice)
            
            # Generate output filename
            base_name = Path(filepath).stem
            output_file = f"output/{base_name}_podcast.mp3"
            
            custom_name = input(f"\nOutput filename (default: {output_file}): ").strip()
            if custom_name:
                output_file = custom_name
            
            # Generate audio
            self.generate_audio(text, output_file, voice['Name'], engine)
            
        except Exception as e:
            print(f"Error reading file: {e}")
    
    def select_voice(self):
        """Interactive voice selection"""
        print("\n🎙️  SELECT VOICE:")
        
        # Show popular voices first
        popular = ['Joanna', 'Matthew', 'Amy', 'Brian', 'Emma', 'Justin']
        print("\nPopular Voices:")
        for i, name in enumerate(popular, 1):
            print(f"{i}. {name}")
        
        print(f"{len(popular) + 1}. See all voices")
        
        try:
            choice = int(input("\nYour choice: "))
            if 1 <= choice <= len(popular):
                voice_name = popular[choice - 1]
                # Find voice details
                for voices in self.voices.values():
                    for v in voices:
                        if v['Name'] == voice_name:
                            return v
            elif choice == len(popular) + 1:
                return self.select_from_all_voices()
            else:
                print("Invalid choice!")
                return None
        except ValueError:
            print("Please enter a number!")
            return None
    
    def select_from_all_voices(self):
        """Show all voices for selection"""
        all_voices = []
        for voices in self.voices.values():
            all_voices.extend(voices)
        
        print("\nAll Available Voices:")
        for i, voice in enumerate(all_voices, 1):
            print(f"{i}. {voice['Name']:15} | {voice['LanguageCode']:10} | {voice['Gender']}")
        
        try:
            choice = int(input("\nSelect voice number: "))
            if 1 <= choice <= len(all_voices):
                return all_voices[choice - 1]
            else:
                print("Invalid choice!")
                return None
        except ValueError:
            print("Please enter a number!")
            return None
    
    def select_engine(self, voice):
        """Select neural or standard engine"""
        supported = voice.get('SupportedEngines', [])
        
        if 'neural' in supported and 'standard' in supported:
            print("\nEngine:")
            print("1. Neural (more natural, recommended)")
            print("2. Standard")
            
            try:
                choice = int(input("Your choice (default: 1): ").strip() or "1")
                return 'neural' if choice == 1 else 'standard'
            except ValueError:
                return 'neural'
        elif 'neural' in supported:
            return 'neural'
        else:
            return 'standard'
    
    def generate_audio(self, text, output_file, voice_id, engine):
        """Generate the audio file"""
        try:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            
            print("\n🎵 Generating audio...")
            print(f"   Voice: {voice_id}")
            print(f"   Engine: {engine}")
            print(f"   Text length: {len(text)} characters")
            
            # Check if text is too long
            max_chars = 3000 if engine == 'neural' else 6000
            if len(text) > max_chars:
                print(f"\n⚠️  Text is too long ({len(text)} chars, max {max_chars})")
                print("Consider splitting into multiple files.")
                return
            
            response = self.polly_client.synthesize_speech(
                Text=text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine
            )
            
            with open(output_file, 'wb') as f:
                f.write(response['AudioStream'].read())
            
            file_size = os.path.getsize(output_file)
            print(f"\n✅ SUCCESS!")
            print(f"   File: {output_file}")
            print(f"   Size: {file_size / 1024:.2f} KB")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    def sample_voices_mode(self):
        """Generate samples with different voices"""
        sample_text = input("\nEnter sample text (or press Enter for default): ").strip()
        if not sample_text:
            sample_text = "Hello, this is a sample of my voice. How do you like the way I sound?"
        
        voices_to_try = ['Joanna', 'Matthew', 'Amy', 'Brian']
        
        print(f"\n🎵 Generating samples for {len(voices_to_try)} voices...")
        
        for voice_name in voices_to_try:
            output_file = f"output/sample_{voice_name.lower()}.mp3"
            self.generate_audio(sample_text, output_file, voice_name, 'neural')
    
    def run(self):
        """Main loop"""
        while True:
            self.display_menu()
            
            try:
                choice = input("Select option: ").strip()
                
                if choice == '1':
                    self.text_input_mode()
                elif choice == '2':
                    self.file_input_mode()
                elif choice == '3':
                    self.list_voices_menu()
                elif choice == '4':
                    self.sample_voices_mode()
                elif choice == '5':
                    print("\n💡 SSML features are in podcast_generator_advanced.py")
                    print("   Run that script for SSML demonstrations!")
                elif choice == '6':
                    print("\n👋 Goodbye!")
                    break
                else:
                    print("\n❌ Invalid option!")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    cli = PodcastCLI()
    cli.run()