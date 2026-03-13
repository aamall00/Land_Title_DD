import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Send, Loader, Bot, User, BookOpen, ChevronDown, ChevronUp } from 'lucide-react'
import { api } from '../../lib/api'

const SUGGESTED_QUESTIONS = [
  'Who are all the previous owners of this property?',
  'Are there any outstanding loans or mortgages on the EC?',
  'Does the survey number match across all documents?',
  'Is there any litigation or court case on this property?',
  'What is the current land use classification in the RTC?',
  'Has the Khata been transferred to the current owner?',
  'What is the registered area in the Sale Deed?',
  'Is there a valid BBMP/BDA layout approval?',
]

function SourceBadge({ source }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-slate-200 rounded-lg text-xs">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 w-full px-2.5 py-1.5 text-left hover:bg-slate-50"
      >
        <BookOpen className="w-3 h-3 text-slate-400" />
        <span className="font-medium text-slate-600 truncate flex-1">{source.original_name}</span>
        <span className="badge bg-slate-100 text-slate-600">{source.doc_type}</span>
        <span className="text-slate-400">{(source.similarity * 100).toFixed(0)}%</span>
        {open ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-2.5 pb-2 text-slate-600 border-t border-slate-100 pt-1.5 leading-relaxed">
          {source.chunk_text}
        </div>
      )}
    </div>
  )
}

function Message({ msg }) {
  const isBot = msg.role === 'assistant'
  return (
    <div className={`flex gap-3 ${isBot ? '' : 'flex-row-reverse'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5
        ${isBot ? 'bg-brand-600' : 'bg-slate-300'}`}>
        {isBot
          ? <Bot className="w-3.5 h-3.5 text-white" />
          : <User className="w-3.5 h-3.5 text-slate-600" />}
      </div>

      <div className={`flex-1 max-w-[85%] ${isBot ? '' : 'items-end flex flex-col'}`}>
        <div className={`rounded-xl px-4 py-3 text-sm
          ${isBot
            ? 'bg-white border border-slate-200 text-slate-800'
            : 'bg-brand-600 text-white'}`}
        >
          {isBot
            ? <ReactMarkdown className="prose prose-sm max-w-none prose-slate">
                {msg.content}
              </ReactMarkdown>
            : msg.content
          }
        </div>

        {isBot && msg.sources?.length > 0 && (
          <div className="mt-2 space-y-1 w-full">
            <p className="text-xs text-slate-400 px-1">Sources:</p>
            {msg.sources.map((s, i) => (
              <SourceBadge key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function QueryInterface({ propertyId }) {
  const [messages, setMessages]   = useState([])
  const [input, setInput]         = useState('')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const bottomRef = useRef(null)

  // Load history
  useEffect(() => {
    if (historyLoaded) return
    api.queries.history(propertyId, 30).then(history => {
      if (history?.length) {
        const msgs = []
        // history is newest-first; reverse
        ;[...history].reverse().forEach(q => {
          msgs.push({ role: 'user',      content: q.question })
          msgs.push({ role: 'assistant', content: q.answer, sources: q.sources })
        })
        setMessages(msgs)
      }
      setHistoryLoaded(true)
    }).catch(() => setHistoryLoaded(true))
  }, [propertyId, historyLoaded])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send(question) {
    const q = question || input.trim()
    if (!q || loading) return
    setInput('')
    setError('')
    setMessages(prev => [...prev, { role: 'user', content: q }])
    setLoading(true)

    try {
      const result = await api.queries.ask(propertyId, { question: q })
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: result.answer,
        sources: result.sources,
      }])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Message area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !loading && (
          <div className="space-y-4">
            <div className="text-center text-slate-400 text-sm py-4">
              <Bot className="w-8 h-8 mx-auto mb-2 text-slate-300" />
              Ask anything about your uploaded documents
              <p className="text-xs mt-1">
                Supports English and Kannada
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2">
              {SUGGESTED_QUESTIONS.map(q => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-left text-xs px-3 py-2 rounded-lg border border-slate-200
                             text-slate-600 hover:border-brand-300 hover:text-brand-700
                             hover:bg-brand-50 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => <Message key={i} msg={m} />)}

        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-white" />
            </div>
            <div className="bg-white border border-slate-200 rounded-xl px-4 py-3">
              <Loader className="w-4 h-4 text-brand-600 animate-spin" />
            </div>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-slate-200 p-3 bg-white">
        <div className="flex gap-2">
          <input
            className="input flex-1 text-sm"
            placeholder="Ask about ownership, encumbrances, area, approvals..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
            disabled={loading}
          />
          <button
            onClick={() => send()}
            disabled={loading || !input.trim()}
            className="btn-primary px-3"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
