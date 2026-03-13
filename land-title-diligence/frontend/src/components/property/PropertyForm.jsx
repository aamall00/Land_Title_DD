import { useState } from 'react'
import { X } from 'lucide-react'
import { api } from '../../lib/api'

const TALUKS = [
  'Bangalore North', 'Bangalore South', 'Bangalore East', 'Yelahanka',
  'Anekal', 'Devanahalli', 'Doddaballapur', 'Nelamangala', 'Kanakapura', 'Ramanagara',
]

export default function PropertyForm({ onCreated, onClose }) {
  const [form, setForm] = useState({
    property_name: '',
    survey_number: '',
    khata_number: '',
    taluk: '',
    hobli: '',
    village: '',
    district: 'Bangalore Urban',
    total_area: '',
    address: '',
    notes: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.property_name.trim()) {
      setError('Property name is required')
      return
    }
    setLoading(true)
    setError('')
    try {
      const created = await api.properties.create(form)
      onCreated?.(created)
      onClose?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-5 border-b border-slate-100">
          <h2 className="font-semibold text-slate-900">Add New Property</h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-slate-100">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-5 space-y-4">
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <div>
            <label className="label">Property Name *</label>
            <input
              className="input"
              placeholder="e.g. Yelahanka New Town Site #45"
              value={form.property_name}
              onChange={e => set('property_name', e.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Survey No. (Sy. No.)</label>
              <input
                className="input"
                placeholder="e.g. 45/2"
                value={form.survey_number}
                onChange={e => set('survey_number', e.target.value)}
              />
            </div>
            <div>
              <label className="label">Khata Number</label>
              <input
                className="input"
                placeholder="e.g. 123/456"
                value={form.khata_number}
                onChange={e => set('khata_number', e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Taluk</label>
              <select
                className="input"
                value={form.taluk}
                onChange={e => set('taluk', e.target.value)}
              >
                <option value="">Select taluk...</option>
                {TALUKS.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Hobli</label>
              <input
                className="input"
                placeholder="e.g. Jala"
                value={form.hobli}
                onChange={e => set('hobli', e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Village</label>
              <input
                className="input"
                placeholder="e.g. Yelahanka"
                value={form.village}
                onChange={e => set('village', e.target.value)}
              />
            </div>
            <div>
              <label className="label">Total Area</label>
              <input
                className="input"
                placeholder="e.g. 2400 sq ft"
                value={form.total_area}
                onChange={e => set('total_area', e.target.value)}
              />
            </div>
          </div>

          <div>
            <label className="label">Address</label>
            <textarea
              className="input resize-none"
              rows={2}
              placeholder="Property address..."
              value={form.address}
              onChange={e => set('address', e.target.value)}
            />
          </div>

          <div>
            <label className="label">Notes</label>
            <textarea
              className="input resize-none"
              rows={2}
              placeholder="Internal notes..."
              value={form.notes}
              onChange={e => set('notes', e.target.value)}
            />
          </div>
        </form>

        <div className="p-5 border-t border-slate-100 flex gap-3 justify-end">
          <button type="button" onClick={onClose} className="btn-secondary">
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="btn-primary"
          >
            {loading ? 'Creating...' : 'Create Property'}
          </button>
        </div>
      </div>
    </div>
  )
}
