import { useState } from 'react'
import { FileText, Trash2, RefreshCw, ChevronDown, ChevronUp, Tag } from 'lucide-react'
import { api } from '../../lib/api'

const STATUS_COLORS = {
  pending:    'bg-slate-100 text-slate-600',
  processing: 'bg-blue-100 text-blue-700',
  ready:      'bg-green-100 text-green-700',
  error:      'bg-red-100 text-red-700',
}

const DOC_TYPE_LABELS = {
  EC:            'EC',
  RTC:           'RTC',
  SALE_DEED:     'Sale Deed',
  KHATA:         'Khata',
  MUTATION:      'Mutation',
  SKETCH:        'Sketch',
  LEGAL_HEIR:    'Legal Heir',
  COURT:         'Court',
  BBMP_APPROVAL: 'BBMP',
  BDA_APPROVAL:  'BDA',
  OTHER:         'Other',
}

const DOC_TYPE_COLORS = {
  EC:            'bg-purple-100 text-purple-700',
  RTC:           'bg-blue-100 text-blue-700',
  SALE_DEED:     'bg-emerald-100 text-emerald-700',
  KHATA:         'bg-amber-100 text-amber-700',
  MUTATION:      'bg-orange-100 text-orange-700',
  SKETCH:        'bg-cyan-100 text-cyan-700',
  LEGAL_HEIR:    'bg-indigo-100 text-indigo-700',
  COURT:         'bg-red-100 text-red-700',
  BBMP_APPROVAL: 'bg-teal-100 text-teal-700',
  BDA_APPROVAL:  'bg-sky-100 text-sky-700',
  OTHER:         'bg-slate-100 text-slate-600',
}

const ALL_DOC_TYPES = Object.keys(DOC_TYPE_LABELS)

function DocumentRow({ doc, propertyId, onDeleted, onTypeChanged }) {
  const [showMeta, setShowMeta] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [changingType, setChangingType] = useState(false)

  async function handleDelete() {
    if (!confirm(`Delete "${doc.original_name}"?`)) return
    setDeleting(true)
    try {
      await api.documents.delete(propertyId, doc.id)
      onDeleted?.(doc.id)
    } catch (err) {
      alert(`Delete failed: ${err.message}`)
    } finally {
      setDeleting(false)
    }
  }

  async function handleTypeChange(e) {
    const newType = e.target.value
    setChangingType(true)
    try {
      const updated = await api.documents.setType(propertyId, doc.id, newType)
      onTypeChanged?.(updated)
    } catch (err) {
      alert(`Type update failed: ${err.message}`)
    } finally {
      setChangingType(false)
    }
  }

  const meta = doc.metadata || {}
  const hasMeta = Object.keys(meta).length > 0

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="flex items-center gap-3 p-3 bg-white hover:bg-slate-50">
        <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-800 truncate">{doc.original_name}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`badge ${STATUS_COLORS[doc.status] || ''}`}>
              {doc.status}
            </span>
            {doc.page_count && (
              <span className="text-xs text-slate-400">{doc.page_count}p</span>
            )}
            {doc.file_size && (
              <span className="text-xs text-slate-400">
                {(doc.file_size / 1024).toFixed(0)}KB
              </span>
            )}
          </div>
        </div>

        {/* Doc type selector */}
        <div className="flex items-center gap-1.5">
          <Tag className="w-3.5 h-3.5 text-slate-400" />
          <select
            className={`text-xs px-2 py-1 rounded-full font-medium border-0 cursor-pointer
              ${DOC_TYPE_COLORS[doc.doc_type] || 'bg-slate-100 text-slate-600'}`}
            value={doc.doc_type}
            onChange={handleTypeChange}
            disabled={changingType}
          >
            {ALL_DOC_TYPES.map(t => (
              <option key={t} value={t}>{DOC_TYPE_LABELS[t]}</option>
            ))}
          </select>
        </div>

        {/* Expand meta */}
        {hasMeta && (
          <button
            onClick={() => setShowMeta(v => !v)}
            className="p-1 rounded text-slate-400 hover:text-slate-600"
          >
            {showMeta ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        )}

        <button
          onClick={handleDelete}
          disabled={deleting}
          className="p-1.5 rounded text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
        >
          {deleting
            ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            : <Trash2 className="w-3.5 h-3.5" />
          }
        </button>
      </div>

      {showMeta && hasMeta && (
        <div className="px-3 pb-3 bg-slate-50 border-t border-slate-100">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2">
            {Object.entries(meta).map(([k, v]) =>
              k !== 'all_years' ? (
                <div key={k} className="flex gap-1.5 text-xs">
                  <span className="text-slate-500 font-medium capitalize">
                    {k.replace(/_/g, ' ')}:
                  </span>
                  <span className="text-slate-700 truncate">{String(v)}</span>
                </div>
              ) : null
            )}
          </div>
        </div>
      )}

      {doc.status === 'error' && doc.error_message && (
        <div className="px-3 py-2 bg-red-50 border-t border-red-100 text-xs text-red-600">
          {doc.error_message}
        </div>
      )}
    </div>
  )
}

export default function DocumentList({ documents, propertyId, onDeleted, onTypeChanged }) {
  if (!documents.length) {
    return (
      <div className="text-center py-8 text-sm text-slate-400">
        <FileText className="w-8 h-8 mx-auto mb-2 text-slate-300" />
        No documents uploaded yet
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {documents.map(doc => (
        <DocumentRow
          key={doc.id}
          doc={doc}
          propertyId={propertyId}
          onDeleted={onDeleted}
          onTypeChanged={onTypeChanged}
        />
      ))}
    </div>
  )
}
