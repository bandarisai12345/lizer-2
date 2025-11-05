"""
Medical Appointment Booking System - Backend
Fixed slot selection and end_time handling
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import uuid
from enum import Enum
import os
from google import generativeai as genai

# Configure Gemini
GOOGLE_API_KEY = "AIzaSyBwB4xeRyC5iPY8jC_tJJgc1Z-FrFbR0lE"
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize FastAPI
app = FastAPI(title="Medical Appointment Booking API")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DATA MODELS
# ============================================================================

class AppointmentType(str, Enum):
    GENERAL = "general_consultation"
    FOLLOWUP = "followup"
    PHYSICAL = "physical_exam"
    SPECIALIST = "specialist_consultation"

class ConversationPhase(str, Enum):
    GREETING = "greeting"
    SELECTING_TYPE = "selecting_appointment_type"
    UNDERSTANDING = "understanding_needs"
    SHOWING_SLOTS = "showing_slots"
    COLLECTING_INFO = "collecting_info"
    CONFIRMING = "confirming"
    COMPLETE = "complete"

class Message(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str
    
class PatientInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    
class BookingDetails(BaseModel):
    appointment_type: Optional[AppointmentType] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None
    selected_slot: Optional[Dict[str, str]] = None

class ConversationState(BaseModel):
    session_id: str
    phase: ConversationPhase
    messages: List[Message]
    patient_info: PatientInfo
    booking_details: BookingDetails
    context: Dict[str, Any]
    collected_info: Dict[str, bool] = {
        "appointment_type": False,
        "reason": False,
        "name": False,
        "email": False,
        "phone": False,
        "date": False,
        "time": False
    }

# ============================================================================
# IN-MEMORY STORAGE
# ============================================================================

# Load schedule data
with open('mock_schedule.json', 'r') as f:
    SCHEDULE_DATA = json.load(f)

# Session storage
sessions: Dict[str, ConversationState] = {}
bookings: Dict[str, Dict] = {}

# Appointment type details
APPOINTMENT_TYPES = {
    "general_consultation": {
        "name": "General Consultation",
        "duration": 30,
        "description": "Standard doctor visit for general health concerns"
    },
    "specialist_consultation": {
        "name": "Specialist Consultation",
        "duration": 60,
        "description": "Extended consultation with a specialist"
    },
    "physical_exam": {
        "name": "Physical Exam",
        "duration": 45,
        "description": "Comprehensive physical examination"
    },
    "followup": {
        "name": "Follow-up",
        "duration": 15,
        "description": "Quick follow-up for previous visit"
    }
}

# ============================================================================
# AGENT TOOLS
# ============================================================================

class AgentTools:
    """Tools available to the intent agent"""
    
    @staticmethod
    def get_available_slots(appointment_type: str, date: Optional[str] = None, 
                           time_preference: Optional[str] = None) -> List[Dict]:
        """Get available appointment slots"""
        try:
            type_schedule = SCHEDULE_DATA.get(appointment_type, {}).get("schedule", {})
            available_slots = []
            
            for day, day_data in type_schedule.items():
                if date and day_data.get("date") != date:
                    continue
                    
                for slot in day_data.get("slots", []):
                    if slot.get("available"):
                        slot_info = {
                            "day": day,
                            "date": day_data.get("date"),
                            "start_time": slot.get("start_time"),
                            "end_time": slot.get("end_time"),
                            "duration": SCHEDULE_DATA[appointment_type]["duration_minutes"]
                        }
                        
                        # Apply time preference filter
                        if time_preference:
                            hour = int(slot["start_time"].split(":")[0])
                            if time_preference.lower() in ["morning", "am"] and hour >= 12:
                                continue
                            elif time_preference.lower() in ["afternoon", "pm"] and (hour < 12 or hour >= 17):
                                continue
                            elif time_preference.lower() == "evening" and hour < 17:
                                continue
                                
                        available_slots.append(slot_info)
            
            return available_slots[:10]
        except Exception as e:
            print(f"Error getting slots: {e}")
            return []
    
    @staticmethod
    def recommend_appointment_type(reason: str) -> str:
        """Recommend appointment type based on reason"""
        reason_lower = reason.lower()
        
        if any(word in reason_lower for word in ["followup", "follow-up", "follow up", "checkup", "check up", "routine check"]):
            return "followup"
        elif any(word in reason_lower for word in ["physical", "exam", "annual", "complete exam"]):
            return "physical_exam"
        elif any(word in reason_lower for word in ["specialist", "cardiologist", "dermatologist", "neurologist", "serious", "chronic"]):
            return "specialist_consultation"
        else:
            return "general_consultation"
    
    @staticmethod
    def book_appointment(booking_data: Dict) -> Dict:
        """Book an appointment"""
        booking_id = f"APPT-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        confirmation_code = str(uuid.uuid4())[:6].upper()
        
        booking = {
            "booking_id": booking_id,
            "confirmation_code": confirmation_code,
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
            **booking_data
        }
        
        bookings[booking_id] = booking
        return booking

# ============================================================================
# INTENT AGENT
# ============================================================================

class IntentAgent:
    """Main agent that orchestrates the conversation and decides actions"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        self.tools = AgentTools()
        
    def analyze_intent(self, state: ConversationState, user_message: str) -> Dict[str, Any]:
        """Analyze user intent and decide next action"""
        
        # Get conversation history with numbered slots if available
        conversation_history = "\n".join([
            f"{msg.role}: {msg.content}" for msg in state.messages[-8:]
        ])
        
        collected = state.collected_info
        patient = state.patient_info
        booking = state.booking_details
        
        system_prompt = f"""You are analyzing a medical appointment booking conversation with a specific flow.

CONVERSATION FLOW:
1. First: Get reason for visit
2. Then: Show appointment type options and get selection
3. Then: Ask for date/time preference
4. Then: Show available slots
5. Then: Collect patient details (name, phone, email)
6. Finally: Confirm booking

Current State:
- Phase: {state.phase}
- Collected: {json.dumps(collected)}
- Patient: name={patient.name}, email={patient.email}, phone={patient.phone}
- Booking: type={booking.appointment_type}, reason={booking.reason}, date={booking.preferred_date}, time={booking.preferred_time}
- Selected Slot: {booking.selected_slot}

Recent Conversation:
{conversation_history}

User Message: "{user_message}"

Appointment Types Available:
- general_consultation (30 min): For common health concerns, symptoms like headaches, fever, cough
- specialist_consultation (60 min): For serious/chronic conditions, specialized care
- physical_exam (45 min): Annual checkups, comprehensive exams
- followup (15 min): Quick follow-ups for previous visits

Analyze and return JSON with:
{{
    "intent": "provide_reason|select_appointment_type|select_time|provide_info|confirm|new_booking|select_slot",
    "extracted": {{
        "reason": "extracted reason or null",
        "appointment_type": "general_consultation|specialist_consultation|physical_exam|followup or null",
        "name": "extracted name or null",
        "email": "extracted email or null", 
        "phone": "extracted phone or null",
        "date": "YYYY-MM-DD format or null",
        "time_preference": "morning|afternoon|evening or null",
        "specific_slot": {{"date": "YYYY-MM-DD", "start_time": "HH:MM"}} or null,
        "slot_selection": "which slot number user selected (1-5) or null"
    }},
    "next_action": "ask_reason|show_appointment_types|ask_time_preference|show_slots|collect_name|collect_phone|collect_email|confirm_booking|restart",
    "ready_to_book": true/false,
    "is_greeting": true/false
}}

Rules:
1. If user greets ("hello", "hi"), set is_greeting=true, next_action="ask_reason"
2. If user provides reason but no type selected, next_action="show_appointment_types"
3. Extract appointment type from keywords (e.g., "follow-up" → followup, "physical" → physical_exam)
4. If appointment type selected, next_action="ask_time_preference"
5. If time preference given, next_action="show_slots"
6. If slot selected and have type, next_action starts collecting: "collect_name" → "collect_phone" → "collect_email"
7. ready_to_book=true ONLY when we have: name, email, phone, selected_slot
8. If user says "new appointment" or "book another" after completion, set next_action="restart"
9. Parse dates like "tomorrow", "Jan 16", "Wednesday", "06-11-2025"
10. Parse times like "2:00 PM", "afternoon", "morning", "1PM" as {{date: "YYYY-MM-DD", start_time: "13:00"}}
11. When user selects a slot number (e.g., "1", "first", "option 1"), set slot_selection to that number
12. When extracting specific_slot, ONLY include date and start_time, NOT end_time (it will be looked up)

Respond ONLY with valid JSON."""

        try:
            response = self.model.generate_content(system_prompt)
            result = json.loads(response.text.strip().replace("```json", "").replace("```", ""))
            return result
        except Exception as e:
            print(f"Intent analysis error: {e}")
            return {
                "intent": "unknown",
                "extracted": {},
                "next_action": "ask_reason",
                "ready_to_book": False,
                "is_greeting": False
            }
    
    def generate_response(self, state: ConversationState, intent_analysis: Dict, available_slots: List[Dict]) -> str:
        """Generate natural conversational response"""
        
        conversation_history = "\n".join([
            f"{msg.role}: {msg.content}" for msg in state.messages[-4:]
        ])
        
        collected = state.collected_info
        patient = state.patient_info
        booking = state.booking_details
        next_action = intent_analysis.get('next_action')
        
        # Format slots if available
        slots_text = ""
        if available_slots and next_action == "show_slots":
            slots_text = "\n\nAvailable slots to show:\n"
            for i, slot in enumerate(available_slots[:5], 1):
                slots_text += f"{i}. {slot['day']}, {slot['date']} at {slot['start_time']}\n"
        
        system_prompt = f"""You are a warm, professional medical appointment assistant.

Current Situation:
- Phase: {state.phase}
- What we have: {json.dumps({
    'reason': booking.reason,
    'appointment_type': booking.appointment_type,
    'name': patient.name,
    'email': patient.email,
    'phone': patient.phone,
    'date': booking.preferred_date,
    'time': booking.preferred_time,
    'selected_slot': booking.selected_slot
})}
- Next action: {next_action}

Recent conversation:
{conversation_history}
{slots_text}

Response Guidelines by Action:

ask_reason:
- "I'd be happy to help you schedule an appointment! What's the main reason for your visit today?"

show_appointment_types:
- Acknowledge their reason warmly
- Recommend the most appropriate type based on their reason
- Present ALL 4 options with durations clearly:
  Example: "I understand. For [reason], I'd recommend a [recommended type] ([X] minutes) where the doctor can [what they do]. 
  
  We also have these options:
  • General Consultation (30 min) - For common health concerns
  • Specialist Consultation (60 min) - For serious/chronic conditions  
  • Physical Exam (45 min) - Comprehensive health checkup
  • Follow-up (15 min) - Quick follow-up visit
  
  Which type would work best for you?"

ask_time_preference:
- "Perfect! When would you like to come in? Do you have a preference for morning, afternoon, or evening appointments?"

show_slots:
- Present available slots conversationally
- Format: "Let me check our [morning/afternoon/evening] availability this week. I have these options:"
- List 3-5 slots with full details: day, date, and time
- End with: "Which works best for you?"

collect_name:
- "Great choice! Before I confirm, I'll need a few details. What's your full name?"

collect_phone:
- "Thank you! What's the best phone number to reach you?"

collect_email:
- "And your email address for the confirmation?"

Rules:
- NEVER repeat information already provided
- Keep responses natural and conversational
- Be concise (2-4 sentences unless listing options)
- Don't mention phase or internal state
- Format times as "2:00 PM" not "14:00"

Write ONLY the assistant's response."""

        try:
            response = self.model.generate_content(system_prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Response generation error: {e}")
            return "I'm here to help you schedule your appointment. What brings you in today?"

# ============================================================================
# API ENDPOINTS
# ============================================================================

agent = IntentAgent()

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Main chat endpoint"""
    
    # Get or create session
    if request.session_id not in sessions:
        sessions[request.session_id] = ConversationState(
            session_id=request.session_id,
            phase=ConversationPhase.GREETING,
            messages=[],
            patient_info=PatientInfo(),
            booking_details=BookingDetails(),
            context={},
            collected_info={
                "appointment_type": False,
                "reason": False,
                "name": False,
                "email": False,
                "phone": False,
                "date": False,
                "time": False
            }
        )
    
    state = sessions[request.session_id]
    
    # Check for restart request
    if state.phase == ConversationPhase.COMPLETE:
        if any(word in request.message.lower() for word in ["new", "another", "book", "schedule"]):
            # Reset session
            state.phase = ConversationPhase.GREETING
            state.patient_info = PatientInfo()
            state.booking_details = BookingDetails()
            state.collected_info = {
                "appointment_type": False,
                "reason": False,
                "name": False,
                "email": False,
                "phone": False,
                "date": False,
                "time": False
            }
    
    # Add user message
    user_msg = Message(
        role="user",
        content=request.message,
        timestamp=datetime.now().isoformat()
    )
    state.messages.append(user_msg)
    
    # Analyze intent
    intent_analysis = agent.analyze_intent(state, request.message)
    
    # Update state with extracted data
    extracted = intent_analysis.get("extracted", {})
    
    if extracted.get("reason") and not state.booking_details.reason:
        state.booking_details.reason = extracted["reason"]
        state.collected_info["reason"] = True
        state.phase = ConversationPhase.SELECTING_TYPE
    
    if extracted.get("appointment_type"):
        state.booking_details.appointment_type = extracted["appointment_type"]
        state.collected_info["appointment_type"] = True
        state.phase = ConversationPhase.UNDERSTANDING
    
    if extracted.get("name") and not state.patient_info.name:
        state.patient_info.name = extracted["name"]
        state.collected_info["name"] = True
    
    if extracted.get("phone") and not state.patient_info.phone:
        state.patient_info.phone = extracted["phone"]
        state.collected_info["phone"] = True
    
    if extracted.get("email") and not state.patient_info.email:
        state.patient_info.email = extracted["email"]
        state.collected_info["email"] = True
    
    if extracted.get("date"):
        state.booking_details.preferred_date = extracted["date"]
        state.collected_info["date"] = True
    
    if extracted.get("time_preference"):
        state.booking_details.preferred_time = extracted["time_preference"]
        state.collected_info["time"] = True
        state.phase = ConversationPhase.SHOWING_SLOTS
    
    # Handle specific slot selection
    if extracted.get("specific_slot"):
        slot = extracted["specific_slot"]
        # If the extracted slot doesn't have end_time, find it from available slots
        if "end_time" not in slot and state.booking_details.appointment_type:
            available = agent.tools.get_available_slots(
                state.booking_details.appointment_type,
                date=slot.get("date"),
                time_preference=None
            )
            # Find matching slot
            for avail_slot in available:
                if (avail_slot["date"] == slot.get("date") and 
                    avail_slot["start_time"] == slot.get("start_time")):
                    slot = avail_slot
                    break
        state.booking_details.selected_slot = slot
        state.phase = ConversationPhase.COLLECTING_INFO
    
    # Handle slot selection by number
    elif extracted.get("slot_selection") and state.booking_details.appointment_type:
        slot_num = extracted["slot_selection"]
        available = agent.tools.get_available_slots(
            state.booking_details.appointment_type,
            date=state.booking_details.preferred_date,
            time_preference=state.booking_details.preferred_time
        )
        try:
            slot_idx = int(slot_num) - 1
            if 0 <= slot_idx < len(available):
                state.booking_details.selected_slot = available[slot_idx]
                state.phase = ConversationPhase.COLLECTING_INFO
        except (ValueError, IndexError):
            pass
    
    # Get available slots if needed
    available_slots = []
    next_action = intent_analysis.get("next_action")
    
    if next_action == "show_slots" and state.booking_details.appointment_type:
        available_slots = agent.tools.get_available_slots(
            state.booking_details.appointment_type,
            date=state.booking_details.preferred_date,
            time_preference=state.booking_details.preferred_time
        )
    
    # Check if ready to book
    booking_result = None
    can_book = (
        intent_analysis.get("ready_to_book") and
        state.patient_info.name and 
        state.patient_info.email and 
        state.patient_info.phone and 
        state.booking_details.selected_slot and
        "end_time" in state.booking_details.selected_slot
    )
    
    if can_book:
        # Book the appointment
        apt_type_info = APPOINTMENT_TYPES.get(state.booking_details.appointment_type, {})
        
        booking_data = {
            "appointment_type": state.booking_details.appointment_type,
            "appointment_type_name": apt_type_info.get("name"),
            "duration": apt_type_info.get("duration"),
            "date": state.booking_details.selected_slot["date"],
            "start_time": state.booking_details.selected_slot["start_time"],
            "end_time": state.booking_details.selected_slot["end_time"],
            "patient": {
                "name": state.patient_info.name,
                "email": state.patient_info.email,
                "phone": state.patient_info.phone
            },
            "reason": state.booking_details.reason or "General consultation"
        }
        
        booking_result = agent.tools.book_appointment(booking_data)
        state.phase = ConversationPhase.COMPLETE
        
        # Generate confirmation message
        slot = state.booking_details.selected_slot
        response_text = (
            f"Perfect! All set. Your appointment is confirmed for {slot['day']}, {slot['date']} "
            f"at {slot['start_time']}. You'll receive a confirmation email at {state.patient_info.email} "
            f"with all the details. Your confirmation code is {booking_result['confirmation_code']}."
        )
    else:
        # Generate conversational response
        response_text = agent.generate_response(state, intent_analysis, available_slots)
    
    # Add assistant message
    assistant_msg = Message(
        role="assistant",
        content=response_text,
        timestamp=datetime.now().isoformat()
    )
    state.messages.append(assistant_msg)
    
    return {
        "response": response_text,
        "phase": state.phase,
        "intent": intent_analysis.get("intent"),
        "available_slots": available_slots if not can_book else [],
        "booking": booking_result,
        "patient_info": state.patient_info.model_dump(),
        "booking_details": state.booking_details.model_dump(),
        "next_action": next_action,
        "appointment_types": APPOINTMENT_TYPES if next_action == "show_appointment_types" else None
    }

@app.post("/api/select-slot")
async def select_slot(session_id: str, slot: Dict):
    """Select a specific time slot"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    state = sessions[session_id]
    state.booking_details.selected_slot = slot
    state.booking_details.preferred_date = slot["date"]
    state.phase = ConversationPhase.COLLECTING_INFO
    
    return {"status": "success", "selected_slot": slot}

@app.get("/api/bookings/{booking_id}")
async def get_booking(booking_id: str):
    """Get booking details"""
    if booking_id not in bookings:
        raise HTTPException(status_code=404, detail="Booking not found")
    return bookings[booking_id]

@app.post("/api/reset-session")
async def reset_session(session_id: str):
    """Reset a session for new booking"""
    if session_id in sessions:
        state = sessions[session_id]
        state.phase = ConversationPhase.GREETING
        state.patient_info = PatientInfo()
        state.booking_details = BookingDetails()
        state.collected_info = {
            "appointment_type": False,
            "reason": False,
            "name": False,
            "email": False,
            "phone": False,
            "date": False,
            "time": False
        }
        return {"status": "reset"}
    return {"status": "not_found"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)