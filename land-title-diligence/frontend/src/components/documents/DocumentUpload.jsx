import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, X, CheckCircle, AlertCircle, Loader } from 'lucide-react'
import { api } from '../../lib/api'

const DOC_TYPES = [
  { value: 'EC',            label: 'EC — Encumbrance Certificate' },
  { value: 'RTC',           label: 'RTC / Pahani' },
  { value: 'SALE_DEED',     label: 'Sale Deed' },
  { value: 'KHATA',         label: 'Khata Certificate / Extract' },
  { value: 'MUTATION',      label: 'Mutation Register' },
  { value: 'SKETCH',        label: 'Survey Sketch / FMB' },
  { value: 'LEGAL_HEIR',    label: 'Legal Heir Certificate' },
  { value: 'COURT',         label: 'Court / Litigation Record' },
  { value: 'BBMP_APPROVAL', label: 'BBMP Plan Approval' },
  { value: 'BDA_APPROVAL',  label: 'BDA Layout Approval' },
  { value: 'OTHER',         label: 'Other Document' },
]

function FileRow({ file, onRemove, onTypeChange }) {
  return (
    <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-200">
      <FileText className="w-4 h-4 text-slate-400 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-700 truncate">{file.file.name}</p>
        <p className="text-xs text-slate-400">{(file.file.size / 1024).toFixed(1)} KB</p>
      </div>
      <select
        className="text-xs border border-slate-300 rounded px-2 py-1 bg-white"
        value={file.docType}
        onChange={e => onTypeChange(file.id, e.target.value)}
      >
        {DOC_TYPES.map(t => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>
      <div className="w-5 flex-shrink-0">
        {file.status === 'uploading' && <Loader className="w-4 h-4 text-brand-600 animate-spin" />}
        {file.status === 'done'      && <CheckCircle className="w-4 h-4 text-green-600" />}
        {file.status === 'error'     && <AlertCircle className="w-4 h-4 text-red-600" title={file.error} />}
        {file.status === 'pending'   && (
          <button onClick={() => onRemove(file.id)} className="text-slate-400 hover:text-red-500">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}

export default function DocumentUpload({ propertyId, onUploaded }) {
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((accepted) => {
    const newFiles = accepted.map(f => ({
      id:      Math.random().toString(36).slice(2),
      file:    f,
      docType: 'OTHER',
      status:  'pending',
      error:   null,
    }))
    setFiles(prev => [...prev, ...newFiles])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf':  ['.pdf'],
      'image/png':        ['.png'],
      'image/jpeg':       ['.jpg', '.jpeg'],
      'image/tiff':       ['.tif', '.tiff'],
    },
    maxSize: 50 * 1024 * 1024,
  })

  function removeFile(id) {
    setFiles(prev => prev.filter(f => f.id !== id))
  }

  function setType(id, docType) {
    setFiles(prev => prev.map(f => f.id === id ? { ...f, docType } : f))
  }

  async function uploadAll() {
    const pending = files.filter(f => f.status === 'pending')
    if (!pending.length) return
    setUploading(true)

    for (const item of pending) {
      setFiles(prev => prev.map(f => f.id === item.id ? { ...f, status: 'uploading' } : f))
      try {
        const formData = new FormData()
        formData.append('file', item.file)
        formData.append('doc_type', item.docType)
        const doc = await api.documents.upload(propertyId, formData)
        setFiles(prev => prev.map(f => f.id === item.id ? { ...f, status: 'done' } : f))
        onUploaded?.(doc)
      } catch (err) {
        setFiles(prev => prev.map(f =>
          f.id === item.id ? { ...f, status: 'error', error: err.message } : f
        ))
      }
    }
    setUploading(false)
  }

  const pendingCount = files.filter(f => f.status === 'pending').length

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-brand-400 bg-brand-50'
            : 'border-slate-300 hover:border-brand-400 hover:bg-slate-50'
          }`}
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <p className="text-sm font-medium text-slate-700">
          {isDragActive ? 'Drop files here...' : 'Drag & drop or click to upload'}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          PDF, PNG, JPG, TIFF — up to 50MB per file
        </p>
        <p className="text-xs text-slate-400">
          Supports Kannada + English documents
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map(f => (
            <FileRow
              key={f.id}
              file={f}
              onRemove={removeFile}
              onTypeChange={setType}
            />
          ))}

          <div className="flex justify-end gap-3 pt-1">
            <button
              onClick={() => setFiles([])}
              className="btn-secondary text-xs"
              disabled={uploading}
            >
              Clear All
            </button>
            <button
              onClick={uploadAll}
              disabled={uploading || pendingCount === 0}
              className="btn-primary text-xs"
            >
              {uploading
                ? 'Uploading...'
                : `Upload ${pendingCount} file${pendingCount !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
