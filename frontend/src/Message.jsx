import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * MetaCard — displayed inside every assistant-message container.
 * All data-testid attributes required by the assignment are present.
 */
function MetaCard({ metadata }) {
  const { resolution_source, model, latency_ms, input_tokens, output_tokens } = metadata;
  const isCache = resolution_source === 'LLM_CACHE';

  return (
    <div className="meta-card">
      <span
        className={`meta-badge ${isCache ? 'cache' : 'live'}`}
        data-testid="meta-source"
      >
        {isCache ? '⚡ LLM_CACHE' : '🌐 LIVE_INFERENCE'}
      </span>

      <span className="meta-item">
        Model: <span data-testid="meta-model">{model}</span>
      </span>

      <span className="meta-item">
        Latency: <span data-testid="meta-latency">{latency_ms} ms</span>
      </span>

      <span className="meta-item">
        In: <span data-testid="meta-input-tokens">{input_tokens}</span>
      </span>

      <span className="meta-item">
        Out: <span data-testid="meta-output-tokens">{output_tokens}</span>
      </span>
    </div>
  );
}

/**
 * A single chat message bubble (user, assistant, or error).
 */
export default function Message({ msg }) {
  const isUser = msg.role === 'user';
  const isError = msg.role === 'error';
  const isLoading = msg.role === 'loading';

  if (isLoading) {
    return (
      <div className="message-row assistant">
        <div className="avatar ai">🤖</div>
        <div className="message-col">
          <div className="bubble assistant loading-bubble">
            <div className="dot" />
            <div className="dot" />
            <div className="dot" />
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="message-row assistant">
        <div className="avatar ai">⚠️</div>
        <div className="message-col">
          <div className="bubble error">{msg.content}</div>
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="message-row user">
        <div className="message-col">
          <div className="bubble user">{msg.content}</div>
        </div>
        <div className="avatar usr">👤</div>
      </div>
    );
  }

  // Assistant message — must have data-testid="assistant-message" on container
  return (
    <div className="message-row assistant" data-testid="assistant-message">
      <div className="avatar ai">🤖</div>
      <div className="message-col">
        <div className="bubble assistant">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.content}
          </ReactMarkdown>
        </div>
        {msg.metadata && <MetaCard metadata={msg.metadata} />}
      </div>
    </div>
  );
}
