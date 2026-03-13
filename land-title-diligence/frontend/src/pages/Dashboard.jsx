import { useState, useEffect } from 'react'
import { Plus, Search, Building2 } from 'lucide-react'
import Header from '../components/layout/Header'
import PropertyCard from '../components/property/PropertyCard'
import PropertyForm from '../components/property/PropertyForm'
import { api } from '../lib/api'

export default function Dashboard() {
  const [properties, setProperties] = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState('')
  const [showForm, setShowForm]     = useState(false)
  const [search, setSearch]         = useState('')

  useEffect(() => {
    api.properties.list()
      .then(setProperties)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function handleCreated(property) {
    setProperties(prev => [property, ...prev])
  }

  function handleDeleted(id) {
    setProperties(prev => prev.filter(p => p.id !== id))
  }

  const filtered = properties.filter(p =>
    !search ||
    p.property_name.toLowerCase().includes(search.toLowerCase()) ||
    p.survey_number?.toLowerCase().includes(search.toLowerCase()) ||
    p.taluk?.toLowerCase().includes(search.toLowerCase()) ||
    p.village?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-6">
        {/* Page title */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-900">Properties</h1>
            <p className="text-sm text-slate-500">
              {properties.length} propert{properties.length !== 1 ? 'ies' : 'y'} under review
            </p>
          </div>
          <button onClick={() => setShowForm(true)} className="btn-primary self-start sm:self-auto">
            <Plus className="w-4 h-4" />
            Add Property
          </button>
        </div>

        {/* Search */}
        {properties.length > 3 && (
          <div className="relative mb-4">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              className="input pl-9 max-w-sm"
              placeholder="Search by name, survey no, taluk..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
        )}

        {/* States */}
        {error && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4">
            {error}
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="card p-5 animate-pulse">
                <div className="h-4 bg-slate-200 rounded w-3/4 mb-3" />
                <div className="h-3 bg-slate-100 rounded w-1/2 mb-2" />
                <div className="h-3 bg-slate-100 rounded w-2/3" />
              </div>
            ))}
          </div>
        )}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-16">
            <Building2 className="w-12 h-12 mx-auto text-slate-300 mb-3" />
            {search ? (
              <p className="text-slate-500">No properties match "{search}"</p>
            ) : (
              <>
                <p className="text-slate-600 font-medium">No properties yet</p>
                <p className="text-slate-400 text-sm mt-1">
                  Add your first property to start the due diligence process
                </p>
                <button
                  onClick={() => setShowForm(true)}
                  className="btn-primary mt-4 mx-auto"
                >
                  <Plus className="w-4 h-4" />
                  Add Property
                </button>
              </>
            )}
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map(p => (
              <PropertyCard key={p.id} property={p} onDeleted={handleDeleted} />
            ))}
          </div>
        )}
      </main>

      {showForm && (
        <PropertyForm
          onCreated={handleCreated}
          onClose={() => setShowForm(false)}
        />
      )}
    </div>
  )
}
