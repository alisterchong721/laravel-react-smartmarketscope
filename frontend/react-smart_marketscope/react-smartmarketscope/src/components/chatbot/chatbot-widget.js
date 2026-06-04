import React, { useEffect, useRef, useState } from 'react';
import { useSelector } from 'react-redux';
import axios from 'axios';
import { API_URL } from '../../config/api';
import './chatbot-widget.css';

const SESSION_STORAGE_KEY = 'smartmarketscope_chat_session_id';

const starterPrompts = [
  'Summarize the latest dashboard bias',
  'What does the latest EURUSD sentiment show?',
  'Review my recent trading journal performance',
];

const ChatbotWidget = () => {
  const { isAuthenticated } = useSelector((state) => state.auth);
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        'Ask me about SmartMarketScope data, sentiment, fundamentals, news, COT, retail positioning, or your trading journal.',
    },
  ]);
  const [sessionId, setSessionId] = useState(() =>
    localStorage.getItem(SESSION_STORAGE_KEY)
  );
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const hasToken = Boolean(localStorage.getItem('token'));
  const shouldShow = isAuthenticated || hasToken;

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isSending]);

  if (!shouldShow) {
    return null;
  }

  const sendMessage = async (messageText = input) => {
    const trimmed = messageText.trim();

    if (!trimmed || isSending) {
      return;
    }

    const token = localStorage.getItem('token');
    const userMessage = { role: 'user', content: trimmed };

    setMessages((current) => [...current, userMessage]);
    setInput('');
    setError('');
    setIsSending(true);

    try {
      const response = await axios.post(
        `${API_URL}/chatbot/message`,
        {
          message: trimmed,
          session_id: sessionId,
        },
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );

      const data = response.data?.data;

      if (!response.data?.success || !data?.assistant_message) {
        throw new Error(response.data?.message || 'The chatbot did not return a response.');
      }

      if (data.session_id) {
        const nextSessionId = String(data.session_id);
        setSessionId(nextSessionId);
        localStorage.setItem(SESSION_STORAGE_KEY, nextSessionId);
      }

      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: data.assistant_message.content,
          contextStatus: data.context_status,
        },
      ]);
    } catch (requestError) {
      const message =
        requestError.response?.data?.message ||
        requestError.message ||
        'Unable to contact the chatbot right now.';

      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content:
            'I could not get the latest SmartMarketScope context for that request. Please try again in a moment.',
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const startNewChat = () => {
    localStorage.removeItem(SESSION_STORAGE_KEY);
    setSessionId(null);
    setError('');
    setMessages([
      {
        role: 'assistant',
        content:
          'New chat started. Ask me anything related to SmartMarketScope.',
      },
    ]);
  };

  return (
    <div className={`sms-chatbot ${isOpen ? 'sms-chatbot--open' : ''}`}>
      {isOpen && (
        <section className="sms-chatbot__panel" aria-label="SmartMarketScope chatbot">
          <header className="sms-chatbot__header">
            <div>
              <p className="sms-chatbot__eyebrow">SmartMarketScope AI</p>
              <h2>Site Assistant</h2>
            </div>
            <div className="sms-chatbot__actions">
              <button type="button" onClick={startNewChat}>
                New
              </button>
              <button type="button" onClick={() => setIsOpen(false)} aria-label="Close chatbot">
                x
              </button>
            </div>
          </header>

          <div className="sms-chatbot__messages">
            {messages.map((message, index) => (
              <article
                className={`sms-chatbot__message sms-chatbot__message--${message.role}`}
                key={`${message.role}-${index}`}
              >
                <span>{message.role === 'user' ? 'You' : 'Assistant'}</span>
                <p>{message.content}</p>
              </article>
            ))}

            {isSending && (
              <article className="sms-chatbot__message sms-chatbot__message--assistant">
                <span>Assistant</span>
                <p>Checking latest site data...</p>
              </article>
            )}

            <div ref={messagesEndRef} />
          </div>

          {messages.length === 1 && (
            <div className="sms-chatbot__starters">
              {starterPrompts.map((prompt) => (
                <button type="button" key={prompt} onClick={() => sendMessage(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>
          )}

          {error && <p className="sms-chatbot__error">{error}</p>}

          <form
            className="sms-chatbot__form"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage();
            }}
          >
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about latest site data..."
              rows={2}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button type="submit" disabled={isSending || !input.trim()}>
              Send
            </button>
          </form>
        </section>
      )}

      <button
        type="button"
        className="sms-chatbot__launcher"
        onClick={() => setIsOpen((current) => !current)}
        aria-label="Open SmartMarketScope chatbot"
      >
        <svg
          aria-hidden="true"
          className="sms-chatbot__launcher-icon"
          fill="none"
          viewBox="0 0 28 28"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M8.4 5.2h11.2c3 0 5.4 2.4 5.4 5.4v5.2c0 3-2.4 5.4-5.4 5.4h-4.8l-5.1 3.1c-.8.5-1.7-.1-1.7-1v-2.1c-2.8-.2-5-2.5-5-5.4v-5.2c0-3 2.4-5.4 5.4-5.4Z"
            stroke="currentColor"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
          />
          <path
            d="M9.8 13.4h.1M14 13.4h.1M18.2 13.4h.1"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="3"
          />
          <path
            d="M10.2 9.4c.4-1.2 1.7-2.1 3.8-2.1s3.4.9 3.8 2.1"
            stroke="currentColor"
            strokeLinecap="round"
            strokeWidth="1.7"
          />
        </svg>
      </button>
    </div>
  );
};

export default ChatbotWidget;
