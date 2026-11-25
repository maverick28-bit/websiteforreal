import { useState, useRef, useEffect, useCallback } from 'react';
import Message from './Message.jsx';
import { sendMessage, fetchHealth } from './api.js';
import { generateSessionId, formatError } from './utils.js';

// Generate a fresh session ID on every page load
const SESSION_ID = generateSessionId();

const SUGGESTED_PROMPTS = [
  'What is quantum computing?',
  'Write a Python hello world',
  'Explain black holes simply',
  'How does HTTPS work?',
];

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState('You are a helpful AI assistant.');
  const [health, setHealth] = useState(null);

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // ── Health poll ──────────────────────────────────────────────────────────
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const h = await fetchHealth();
        setHealth(h);
      } catch {
        setHealth(null);
      }
    };
    checkHealth();
    const id = setInterval(checkHealth, 30000);
    return () => clearInterval(id);
  }, []);

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Send handler ─────────────────────────────────────────────────────────
  const handleSend = useCallback(async (text) => {
    const trimmed = (text || input).trim();
    if (!trimmed || isLoading) return;

    // Add user message + loading indicator
    setMessages(prev => [
      ...prev,
      { role: 'user', content: trimmed },
      { role: 'loading', id: 'loading' },
    ]);
    setInput('');
    setIsLoading(true);

    try {
      const data = await sendMessage({
        sessionId: SESSION_ID,
        message: trimmed,
        systemPrompt,
      });

      setMessages(prev => [
        // Remove loading bubble
        ...prev.filter(m => m.id !== 'loading'),
        {
          role: 'assistant',
          content: data.reply,
          metadata: data.metadata,
        },
      ]);
    } catch (err) {
      const errorText = formatError(err);
      setMessages(prev => [
        ...prev.filter(m => m.id !== 'loading'),
        { role: 'error', content: errorText },
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }, [input, isLoading, systemPrompt]);

  // ── Keyboard handler ─────────────────────────────────────────────────────
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    window.location.reload();
  };

  const hasMessages = messages.some(m => m.role !== 'loading');

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">🤖</div>
          <div>
            <h1>AI Chatbot</h1>
            <div className="session-id">Session: {SESSION_ID.slice(0, 20)}…</div>
          </div>
        </div>
        <div className="header-actions">
          {health !== null && (
            <span className={`health-badge ${health.status === 'ok' ? 'health-ok' : 'health-err'}`}>
              {health.status === 'ok'
                ? `✓ ${health.keys_configured} keys`
                : '✗ offline'}
            </span>
          )}
          <button className="btn-icon" onClick={handleNewChat} title="New conversation">
            ✦ New Chat
          </button>
        </div>
      </header>

      {/* ── System prompt bar ── */}
      <div className="system-prompt-bar">
        <label>System:</label>
        <input
          type="text"
          className="system-prompt-input"
          data-testid="system-prompt-input"
          value={systemPrompt}
          onChange={e => setSystemPrompt(e.target.value)}
          placeholder="Enter a custom system prompt…"
          disabled={isLoading || hasMessages}
        />
      </div>

      {/* ── Messages ── */}
      <div className="messages-container">
        {!hasMessages && (
          <div className="welcome">
            <div className="welcome-icon">✨</div>
            <h2>How can I help you today?</h2>
            <p>Start a conversation. All messages in this session are remembered automatically.</p>
            <div className="welcome-tips">
              {SUGGESTED_PROMPTS.map(p => (
                <button
                  key={p}
                  className="welcome-tip"
                  onClick={() => handleSend(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <Message key={idx} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input area ── */}
      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            data-testid="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message AI… (Enter to send, Shift+Enter for new line)"
            rows={1}
            disabled={isLoading}
            style={{ height: 'auto' }}
            onInput={e => {
              e.target.style.height = 'auto';
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
            }}
          />
          <button
            className="send-btn"
            data-testid="send-button"
            onClick={() => handleSend()}
            disabled={isLoading || !input.trim()}
            title="Send message"
          >
            {isLoading ? '…' : '➤'}
          </button>
        </div>
        <div className="input-hint">
          {isLoading ? 'AI is thinking…' : 'Enter ↵ to send · Shift+Enter for new line'}
        </div>
      </div>
    </div>
  );
}
