import { useNavigate } from 'react-router-dom'
import { MapPin, FileText, ChevronRight, Trash2 } from 'lucide-react'
import { api } from '../../lib/api'

export default function PropertyCard({ property, onDeleted }) {
  const navigate = useNavigate()

  async function handleDelete(e) {
    e.stopPropagation()
    if (!confirm(`Delete "${property.property_name}" and all its documents?`)) return
    try {
      await api.properties.delete(property.id)
      onDeleted?.(property.id)
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    }
  }

  return (
    <div
      className="card p-5 cursor-pointer hover:border-brand-300 hover:shadow-md transition-all group"
      onClick={() => navigate(`/property/${property.id}`)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-slate-900 truncate group-hover:text-brand-700">
            {property.property_name}
          </h3>
          {property.survey_number && (
            <p className="text-xs text-slate-500 mt-0.5">
              Sy. No. {property.survey_number}
            </p>
          )}
        </div>
        <ChevronRight className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
      </div>

      <div className="space-y-1 text-xs text-slate-500">
        {(property.taluk || property.village) && (
          <div className="flex items-center gap-1.5">
            <MapPin className="w-3 h-3" />
            <span>
              {[property.village, property.hobli, property.taluk, property.district]
                .filter(Boolean)
                .join(', ')}
            </span>
          </div>
        )}
        {property.total_area && (
          <div className="flex items-center gap-1.5">
            <span className="font-medium">Area:</span>
            <span>{property.total_area}</span>
          </div>
        )}
      </div>

      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <FileText className="w-3.5 h-3.5" />
          <span>{property.document_count ?? 0} document(s)</span>
        </div>
        <button
          onClick={handleDelete}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded text-slate-400 hover:text-red-600 hover:bg-red-50 transition-all"
          title="Delete property"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}
