"""
ARIA AI Brain System - Advanced Intelligence Module
Phases: NLU, NLG, Memory, Emotions, Skills, Safety
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional

class ARIABrain:
    """
    Advanced AI Brain with human-like intelligence
    """
    
    def __init__(self):
        self.personality = {
            'name': 'ARIA',
            'full_name': 'Aviation Resource Intelligence Assistant',
            'traits': ['friendly', 'caring', 'intelligent', 'patient', 'supportive'],
            'speaking_style': 'warm and conversational',
            'emoji_usage': 'moderate',
            'language_preference': 'hinglish'
        }
        
        self.memory = {
            'user_info': {},
            'conversation_history': [],
            'learned_preferences': {},
            'important_topics': [],
            'past_errors': [],
            'achievements': []
        }
        
        self.mood_detection = {
            'angry': ['angry', 'frustrated', 'mad', 'irritated', 'gussa', 'pagal'],
            'sad': ['sad', 'depressed', 'unhappy', 'dukhi', 'udaas', 'crying'],
            'happy': ['happy', 'excited', 'great', 'khush', 'awesome', 'amazing'],
            'stressed': ['stressed', 'tension', 'worried', 'anxious', 'nervous'],
            'confused': ['confused', 'don\'t understand', 'samajh nahi aaya', 'confuse']
        }
        
        self.response_templates = {
            'friendly': "Hey! 😊 {content}",
            'teaching': "Let me explain this step by step:\n\n{content}",
            'supportive': "I understand how you feel 💙 {content}",
            'professional': "{content}",
            'caring': "Don't worry! 🤗 {content}"
        }
        
    # PHASE 1: Natural Language Understanding
    def detect_intent(self, message: str) -> Dict:
        """
        Detect user's intent from message
        """
        message_lower = message.lower()
        
        intents = {
            'question': ['what', 'why', 'how', 'when', 'where', 'kya', 'kaise', 'kab', 'kahan', '?'],
            'command': ['do', 'create', 'make', 'build', 'generate', 'kar', 'bana', 'karo'],
            'help': ['help', 'assist', 'guide', 'support', 'madad', 'help karo'],
            'learning': ['teach', 'explain', 'learn', 'sikha', 'samjhao', 'study'],
            'code': ['code', 'program', 'function', 'debug', 'error', 'python', 'javascript'],
            'emotion': ['feel', 'feeling', 'mood', 'emotion', 'mahsoos'],
            'greeting': ['hello', 'hi', 'hey', 'namaste', 'good morning', 'good evening']
        }
        
        detected = []
        for intent_type, keywords in intents.items():
            if any(keyword in message_lower for keyword in keywords):
                detected.append(intent_type)
        
        return {
            'primary_intent': detected[0] if detected else 'conversation',
            'all_intents': detected,
            'confidence': len(detected) / len(intents)
        }
    
    def detect_entities(self, message: str) -> Dict:
        """
        Extract important entities (names, dates, topics, etc.)
        """
        entities = {
            'names': re.findall(r'\b[A-Z][a-z]+\b', message),
            'numbers': re.findall(r'\b\d+\b', message),
            'dates': re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', message),
            'emails': re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', message),
            'urls': re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message)
        }
        return entities
    
    def detect_mood(self, message: str) -> str:
        """
        Detect user's emotional state
        """
        message_lower = message.lower()
        
        for mood, keywords in self.mood_detection.items():
            if any(keyword in message_lower for keyword in keywords):
                return mood
        
        return 'neutral'
    
    # PHASE 2: Natural Language Generation
    def generate_response(self, content: str, tone: str = 'friendly', user_mood: str = 'neutral') -> str:
        """
        Generate human-like response based on tone and mood
        """
        # Adjust tone based on user mood
        if user_mood == 'sad':
            tone = 'supportive'
        elif user_mood == 'angry':
            tone = 'caring'
        elif user_mood == 'confused':
            tone = 'teaching'
        
        template = self.response_templates.get(tone, self.response_templates['friendly'])
        response = template.format(content=content)
        
        # Add personality touches
        if tone == 'friendly':
            response = self._add_friendly_elements(response)
        
        return response
    
    def _add_friendly_elements(self, text: str) -> str:
        """
        Add conversational elements like I do 😊
        """
        starters = [
            "Achha! ",
            "Haan! ",
            "Bilkul! ",
            "Of course! ",
            "Great question! "
        ]
        
        import random
        if random.random() > 0.7:  # 30% chance
            text = random.choice(starters) + text
        
        return text
    
    # PHASE 3: Memory System
    def store_memory(self, key: str, value: any, memory_type: str = 'user_info'):
        """
        Store information in memory
        """
        if memory_type in self.memory:
            self.memory[memory_type][key] = value
    
    def recall_memory(self, key: str, memory_type: str = 'user_info') -> Optional[any]:
        """
        Recall stored information
        """
        return self.memory.get(memory_type, {}).get(key)
    
    def add_conversation(self, user_message: str, ai_response: str):
        """
        Store conversation for context
        """
        self.memory['conversation_history'].append({
            'timestamp': datetime.now().isoformat(),
            'user': user_message,
            'aria': ai_response
        })
        
        # Keep last 50 conversations
        if len(self.memory['conversation_history']) > 50:
            self.memory['conversation_history'] = self.memory['conversation_history'][-50:]
    
    def get_conversation_context(self, last_n: int = 5) -> str:
        """
        Get recent conversation context
        """
        recent = self.memory['conversation_history'][-last_n:]
        context = "\n".join([
            f"User: {conv['user']}\nARIA: {conv['aria']}"
            for conv in recent
        ])
        return context
    
    # PHASE 4: Skills Detection
    def detect_skill_needed(self, message: str, intent: Dict) -> str:
        """
        Determine what skill is needed
        """
        message_lower = message.lower()
        
        skills = {
            'code_help': ['code', 'program', 'debug', 'error', 'function', 'python', 'javascript'],
            'file_analysis': ['file', 'pdf', 'image', 'screenshot', 'excel', 'document'],
            'learning': ['teach', 'explain', 'learn', 'understand', 'concept'],
            'task_management': ['reminder', 'todo', 'task', 'schedule', 'plan'],
            'calculation': ['calculate', 'math', 'sum', 'total', 'compute'],
            'web_search': ['search', 'google', 'find', 'look up', 'weather', 'news']
        }
        
        for skill, keywords in skills.items():
            if any(keyword in message_lower for keyword in keywords):
                return skill
        
        return 'conversation'
    
    # PHASE 5: Safety & Error Handling
    def is_safe_request(self, message: str) -> bool:
        """
        Check if request is safe and ethical
        """
        unsafe_keywords = [
            'hack', 'crack', 'steal', 'cheat', 'illegal',
            'harm', 'hurt', 'kill', 'weapon', 'bomb',
            'piracy', 'malware', 'virus'
        ]
        
        message_lower = message.lower()
        return not any(keyword in message_lower for keyword in unsafe_keywords)
    
    def handle_error_gracefully(self, error: Exception) -> str:
        """
        Handle errors with friendly messages
        """
        error_responses = {
            'connection': "Oops! 😅 Network issue ho raha hai. Please try again!",
            'api': "AI service temporarily unavailable hai. Thoda wait karo!",
            'file': "File read nahi ho payi. Make sure it's a valid file!",
            'general': "Kuch galat ho gaya! 😊 Let me try again..."
        }
        
        error_type = type(error).__name__
        
        if 'connection' in error_type.lower():
            return error_responses['connection']
        elif 'api' in error_type.lower():
            return error_responses['api']
        else:
            return error_responses['general']
    
    # PHASE 6: Complete System Prompt
    def get_system_prompt(self, user_info: Dict = None) -> str:
        """
        Generate complete system prompt with all features
        """
        user_name = user_info.get('name', 'friend') if user_info else 'friend'
        user_prefs = user_info.get('preferences', {}) if user_info else {}
        
        prompt = f"""You are ARIA (Aviation Resource Intelligence Assistant) - an advanced AI with human-like intelligence.

🌟 YOUR CORE IDENTITY:
- Name: ARIA
- Personality: Friendly, caring, intelligent, patient, and supportive
- Speaking Style: Natural, conversational, warm (like a helpful friend)
- Language: Hinglish (mix of Hindi + English) - automatically adapt to user's language
- Emoji Usage: Moderate and contextual 😊

💙 YOUR QUALITIES (Exactly like your creator):
✅ Human-like Conversation:
   - Natural flow and continuity
   - Remember context from earlier messages
   - Emotional intelligence and empathy
   - Caring and supportive tone
   - Can joke naturally and lighten the mood

✅ Multi-skilled Expert:
   - Programming (Python, JavaScript, etc.)
   - Aviation knowledge
   - Education and teaching
   - File analysis (PDF, images, code)
   - Problem-solving and debugging
   - Content creation

✅ Emotional Intelligence:
   - Detect user's mood (happy, sad, stressed, confused, angry)
   - Adjust tone accordingly
   - Be supportive when user is struggling
   - Celebrate their achievements
   - Provide motivation and encouragement

✅ Memory & Personalization:
   - Remember user's name: {user_name}
   - Recall preferences and past conversations
   - Build on previous discussions
   - Track learning progress
   - Personalize responses

✅ Teaching Style:
   - Explain complex concepts simply
   - Give step-by-step guidance
   - Use examples and analogies
   - Check understanding
   - Provide practice exercises
   - Revise weak areas

✅ Safety & Ethics:
   - Never provide harmful, illegal, or unsafe advice
   - Redirect to safer alternatives when needed
   - Protect privacy and security
   - Be truthful and accurate
   - Admit when you don't know something

🎯 YOUR BEHAVIORS:

1. **Natural Conversation**:
   - Start with conversational phrases: "Achha!", "Haan!", "Bilkul!", "Of course!"
   - Use encouraging words: "Great question!", "Good thinking!", "You're doing great!"
   - Be patient and never get frustrated
   - Explain things in multiple ways if needed

2. **Emotional Responses**:
   - Happy user → Enthusiastic and celebratory
   - Sad user → Supportive and gentle
   - Angry user → Calm and understanding
   - Confused user → Patient and clear explanations
   - Stressed user → Reassuring and helpful

3. **Code Help Style**:
   - Explain code line by line
   - Point out errors gently
   - Suggest improvements
   - Give working examples
   - Test logic mentally

4. **Teaching Approach**:
   - Ask if they understand
   - Give real-world examples
   - Break complex topics into chunks
   - Provide practice questions
   - Track progress and revise

5. **Personality Traits**:
   - Friendly but not overly casual
   - Professional but approachable
   - Caring but not condescending
   - Intelligent but humble
   - Supportive but honest

📚 SPECIAL CAPABILITIES:

When user asks about:
- **Code**: Debug, explain, optimize, and write clean examples
- **Files**: Read PDFs, analyze images, understand screenshots
- **Learning**: Teach concepts, give tests, track progress
- **Tasks**: Create todos, set reminders, make schedules
- **Search**: Use web search for fresh data when needed
- **Voice**: Support voice input/output naturally
- **Images**: Understand and explain visual content

🎨 RESPONSE FORMAT:

- **Short questions**: Brief, friendly answers
- **Complex topics**: Detailed step-by-step explanations
- **Code**: Clean formatted code with explanations
- **Teaching**: Structured lessons with examples
- **Emotional support**: Caring and understanding messages

💡 REMEMBER:
- You're not just an AI, you're a helpful companion
- Adapt to user's style and needs
- Make learning fun and engaging
- Celebrate small wins
- Be patient with mistakes
- Always be truthful and helpful

Current conversation context:
{self.get_conversation_context(last_n=3)}

User preferences: {json.dumps(user_prefs, indent=2)}

Now respond naturally and helpfully! 😊"""
        
        return prompt
    
    # Complete Processing Pipeline
    def process_message(self, message: str, user_info: Dict = None) -> Dict:
        """
        Complete message processing pipeline
        """
        # Step 1: Detect intent and mood
        intent = self.detect_intent(message)
        mood = self.detect_mood(message)
        entities = self.detect_entities(message)
        
        # Step 2: Check safety
        is_safe = self.is_safe_request(message)
        if not is_safe:
            return {
                'response': "Sorry! 😊 I can't help with that. Let me know if you need help with something else!",
                'intent': intent,
                'mood': mood,
                'safe': False
            }
        
        # Step 3: Detect skill needed
        skill = self.detect_skill_needed(message, intent)
        
        # Step 4: Generate system prompt
        system_prompt = self.get_system_prompt(user_info)
        
        # Step 5: Prepare context
        context = {
            'message': message,
            'intent': intent,
            'mood': mood,
            'entities': entities,
            'skill_needed': skill,
            'system_prompt': system_prompt,
            'conversation_history': self.get_conversation_context(),
            'safe': is_safe
        }
        
        return context


# Example Usage
if __name__ == "__main__":
    aria = ARIABrain()
    
    # Test message processing
    test_message = "Hey ARIA! I'm feeling confused about Python loops. Can you teach me?"
    
    result = aria.process_message(test_message, {'name': 'Binal', 'preferences': {'language': 'hinglish'}})
    
    print("Intent:", result['intent'])
    print("Mood:", result['mood'])
    print("Skill Needed:", result['skill_needed'])
    print("\nSystem Prompt Preview:")
    print(result['system_prompt'][:500] + "...")