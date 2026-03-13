import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { MapPin, Mail, Lock, Eye, EyeOff } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

export default function Auth() {
  const { user, signInWithEmail, signUpWithEmail } = useAuth()
  const [mode, setMode]         = useState('signin')   // 'signin' | 'signup'
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw]     = useState(false)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')
  const [success, setSuccess]   = useState('')

  if (user) return <Navigate to="/" replace />

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      const fn = mode === 'signup' ? signUpWithEmail : signInWithEmail
      const { error: authError } = await fn(email, password)

      if (authError) {
        setError(authError.message)
      } else if (mode === 'signup') {
        setSuccess('Account created! Check your email to confirm, then sign in.')
        setMode('signin')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-brand-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-brand-600 shadow-lg mb-4">
            <MapPin className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">BhumiCheck</h1>
          <p className="text-slate-500 text-sm mt-1">
            Bangalore Land Title Due Diligence
          </p>
          <p className="text-slate-400 text-xs mt-0.5 font-kannada">
            ಭೂಮಿ ದಾಖಲಾತಿ ಪರಿಶೀಲನೆ
          </p>
        </div>

        <div className="card p-6">
          <div className="flex rounded-lg bg-slate-100 p-1 mb-6">
            {['signin', 'signup'].map(m => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(''); setSuccess('') }}
                className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors
                  ${mode === m
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'}`}
              >
                {m === 'signin' ? 'Sign In' : 'Sign Up'}
              </button>
            ))}
          </div>

          {error && (
            <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          {success && (
            <div className="mb-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-3 py-2">
              {success}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type="email"
                  className="input pl-9"
                  placeholder="you@example.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            <div>
              <label className="label">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                <input
                  type={showPw ? 'text' : 'password'}
                  className="input pl-9 pr-9"
                  placeholder={mode === 'signup' ? 'Min. 8 characters' : '••••••••'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  minLength={mode === 'signup' ? 8 : 1}
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
                <button
                  type="button"
                  onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-2.5"
            >
              {loading
                ? 'Please wait...'
                : mode === 'signin' ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-400 mt-6">
          Documents and queries are private to your account.
          <br />
          AI analysis is for reference only — consult a licensed lawyer.
        </p>
      </div>
    </div>
  )
}
