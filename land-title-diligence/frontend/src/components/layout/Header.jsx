import { MapPin, LogOut, User } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

export default function Header() {
  const { user, signOut } = useAuth()

  return (
    <header className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
          <MapPin className="w-4 h-4 text-white" />
        </div>
        <div>
          <span className="font-bold text-slate-900 text-base">BhumiCheck</span>
          <span className="ml-2 text-xs text-slate-400 hidden sm:inline">
            Bangalore Land Title Due Diligence
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <User className="w-4 h-4" />
          <span className="hidden sm:inline">{user?.email}</span>
        </div>
        <button
          onClick={signOut}
          className="btn-secondary text-xs"
          title="Sign out"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Sign out</span>
        </button>
      </div>
    </header>
  )
}
