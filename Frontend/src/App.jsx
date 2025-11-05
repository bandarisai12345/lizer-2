import React, { useState, useEffect, useRef } from 'react';
import { Send, Calendar, Loader2, CheckCircle, Clock, User, Mail, Phone, CalendarDays, AlertCircle } from 'lucide-react';

const API_BASE = 'http://localhost:8000/api';

export default function MedicalBookingApp() {
  const [sessionId] = useState(() => `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hello! I'm your medical appointment assistant. I'm here to help you schedule an appointment. What brings you in today?",
      timestamp: new Date().toISOString()
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [booking, setBooking] = useState(null);
  const [error, setError] = useState(null);
  const [showBookingCard, setShowBookingCard] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (booking) {
      setShowBookingCard(true);
    }
  }, [booking]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = input;
    setInput('');
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: currentInput
        })
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        timestamp: new Date().toISOString()
      }]);
      
      if (data.booking) {
        setBooking(data.booking);
      }
    } catch (error) {
      console.error('Error:', error);
      setError(error.message);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "I'm sorry, I encountered an error connecting to the server. Please make sure the backend is running on http://localhost:8000 and try again.",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTime = (time) => {
    const [hours, minutes] = time.split(':');
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour > 12 ? hour - 12 : hour === 0 ? 12 : hour;
    return `${displayHour}:${minutes} ${ampm}`;
  };

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      weekday: 'long', 
      year: 'numeric', 
      month: 'long', 
      day: 'numeric' 
    });
  };

  const handleNewBooking = async () => {
    try {
      await fetch(`${API_BASE}/reset-session?session_id=${sessionId}`, {
        method: 'POST'
      });
      
      setBooking(null);
      setShowBookingCard(false);
      setMessages([{
        role: 'assistant',
        content: "I'd be happy to help you with another appointment! What brings you in today?",
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Error resetting session:', error);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 p-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-t-3xl shadow-xl p-6 border-b-2 border-blue-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-2xl flex items-center justify-center shadow-lg">
                <Calendar className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-800">Medical Appointment Booking</h1>
                <p className="text-sm text-gray-500 flex items-center gap-2 mt-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  AI-Powered Assistant Online
                </p>
              </div>
            </div>
            {booking && (
              <button
                onClick={handleNewBooking}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
              >
                New Booking
              </button>
            )}
          </div>
        </div>

        {/* Booking Confirmation Card */}
        {showBookingCard && booking && (
          <div className="bg-gradient-to-br from-green-50 to-emerald-50 border-x-2 border-green-200 p-6 animate-slideDown">
            <div className="bg-white rounded-2xl shadow-lg p-6 border-2 border-green-200">
              <div className="flex items-start gap-4 mb-6">
                <div className="w-14 h-14 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center shadow-lg flex-shrink-0">
                  <CheckCircle className="w-8 h-8 text-white" />
                </div>
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-green-900 mb-1">
                    Appointment Confirmed!
                  </h2>
                  <p className="text-green-700 text-sm">
                    Your booking has been successfully confirmed
                  </p>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-4 mb-6">
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-200">
                  <div className="flex items-center gap-3 mb-3">
                    <CalendarDays className="w-5 h-5 text-blue-600" />
                    <h3 className="font-semibold text-gray-800">Appointment Details</h3>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-gray-600">Date & Time</p>
                      <p className="font-bold text-gray-900">
                        {formatDate(booking.date)}
                      </p>
                      <p className="font-bold text-blue-600 text-lg">
                        {formatTime(booking.start_time)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-600">Appointment Type</p>
                      <p className="font-semibold text-gray-900">{booking.appointment_type_name}</p>
                      <p className="text-sm text-gray-600 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {booking.duration} minutes
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl p-4 border border-purple-200">
                  <div className="flex items-center gap-3 mb-3">
                    <User className="w-5 h-5 text-purple-600" />
                    <h3 className="font-semibold text-gray-800">Patient Information</h3>
                  </div>
                  <div className="space-y-2">
                    <div className="flex items-start gap-2">
                      <User className="w-4 h-4 text-gray-500 mt-0.5" />
                      <div>
                        <p className="text-xs text-gray-600">Name</p>
                        <p className="font-semibold text-gray-900">{booking.patient.name}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Mail className="w-4 h-4 text-gray-500 mt-0.5" />
                      <div>
                        <p className="text-xs text-gray-600">Email</p>
                        <p className="text-sm text-gray-900">{booking.patient.email}</p>
                      </div>
                    </div>
                    <div className="flex items-start gap-2">
                      <Phone className="w-4 h-4 text-gray-500 mt-0.5" />
                      <div>
                        <p className="text-xs text-gray-600">Phone</p>
                        <p className="text-sm text-gray-900">{booking.patient.phone}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-xl p-4 border border-amber-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-amber-800 font-medium mb-1">Booking Reference</p>
                    <p className="font-mono font-bold text-gray-900">{booking.booking_id}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-amber-800 font-medium mb-1">Confirmation Code</p>
                    <p className="font-mono font-bold text-green-600 text-xl">{booking.confirmation_code}</p>
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-start gap-2 text-sm text-gray-600">
                  <AlertCircle className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <p>
                    A confirmation email has been sent to <strong>{booking.patient.email}</strong>. 
                    Please arrive 10 minutes before your appointment time.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Chat Messages */}
        <div className={`bg-white border-x-2 border-blue-100 ${showBookingCard ? 'h-[400px]' : 'h-[600px]'} overflow-y-auto p-6 space-y-4 scroll-smooth transition-all duration-300`}>
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fadeIn`}
            >
              <div
                className={`max-w-md lg:max-w-lg px-5 py-3.5 rounded-2xl shadow-md ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-br-none'
                    : 'bg-gradient-to-r from-gray-50 to-gray-100 text-gray-800 rounded-bl-none border border-gray-200'
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                <p className={`text-xs mt-2 ${msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'}`}>
                  {new Date(msg.timestamp).toLocaleTimeString([], { 
                    hour: '2-digit', 
                    minute: '2-digit' 
                  })}
                </p>
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="flex justify-start animate-fadeIn">
              <div className="bg-gradient-to-r from-gray-50 to-gray-100 rounded-2xl rounded-bl-none px-5 py-3.5 border border-gray-200 shadow-md">
                <div className="flex gap-2 items-center">
                  <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                  <span className="text-sm text-gray-600">Thinking...</span>
                </div>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border-x-2 border-red-200 p-4 animate-fadeIn">
            <div className="flex items-center gap-2 text-red-700 text-sm">
              <AlertCircle className="w-5 h-5" />
              <p><strong>Error:</strong> {error}</p>
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="bg-white rounded-b-3xl shadow-xl p-5 border-t-2 border-blue-100">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={booking ? "Type 'new booking' to schedule another appointment..." : "Type your message here..."}
              disabled={loading}
              className="flex-1 px-5 py-3.5 border-2 border-gray-200 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:text-gray-500 text-gray-800 placeholder-gray-400 transition-all"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-6 py-3.5 rounded-full hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transition-all duration-300 shadow-lg hover:shadow-xl active:scale-95 flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-gray-500">
            <p className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              Powered by Google Gemini AI
            </p>
            <p className="font-mono text-gray-400">
              Session: {sessionId.slice(0, 15)}...
            </p>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        @keyframes slideDown {
          from {
            opacity: 0;
            transform: translateY(-20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.3s ease-out;
        }
        .animate-slideDown {
          animation: slideDown 0.4s ease-out;
        }
      `}</style>
    </div>
  );
}