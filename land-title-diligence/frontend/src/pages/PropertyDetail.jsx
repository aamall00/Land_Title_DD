import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, MapPin, FileText, MessageSquare, ClipboardList,
  RefreshCw, Info
} from 'lucide-react'
import Header from '../components/layout/Header'
import DocumentUpload from '../components/documents/DocumentUpload'
import DocumentList   from '../components/documents/DocumentList'
import QueryInterface  from '../components/query/QueryInterface'
import ReportView      from '../components/report/ReportView'
import { api } from '../lib/api'

const TABS = [
  { id: 'documents', label: 'Documents',    icon: FileText },
  { id: 'query',     label: 'Ask / Q&A',    icon: MessageSquare },
  { id: 'report',    label: 'Due Diligence Report', icon: ClipboardList },
]

export default function PropertyDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [property,  setProperty]  = useState(null)
  const [documents, setDocuments] = useState([])
  const [reports,   setReports]   = useState([])
  const [tab,       setTab]       = useState('documents')
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState('')
  const [polling,   setPolling]   = useState(false)

  async function load() {
    try {
      const [prop, docs, rpts] = await Promise.all([
        api.properties.get(id),
        api.documents.list(id),
        api.reports.list(id),
      ])
      setProperty(prop)
      setDocuments(docs)
      setReports(rpts)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [id])

  // Poll for processing docs
  useEffect(() => {
    const processing = documents.some(d => d.status === 'processing' || d.status === 'pending')
    if (!processing || polling) return
    setPolling(true)
    const timer = setInterval(async () => {
      try {
        const docs = await api.documents.list(id)
        setDocuments(docs)
        if (!docs.some(d => d.status === 'processing' || d.status === 'pending')) {
          clearInterval(timer)
          setPolling(false)
        }
      } catch { clearInterval(timer); setPolling(false) }
    }, 5000)
    return () => { clearInterval(timer); setPolling(false) }
  }, [documents, id])

  function handleUploaded(doc) {
    setDocuments(prev => [doc, ...prev])
  }

  function handleDeleted(docId) {
    setDocuments(prev => prev.filter(d => d.id !== docId))
  }

  function handleTypeChanged(updated) {
    setDocuments(prev => prev.map(d => d.id === updated.id ? updated : d))
  }

  function handleReportGenerated(report) {
    setReports(prev => [report, ...prev])
  }

  if (loading) return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-600 border-t-transparent" />
      </div>
    </div>
  )

  if (error) return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <div className="flex-1 flex items-center justify-center text-red-600">{error}</div>
    </div>
  )

  const readyCount = documents.filter(d => d.status === 'ready').length

  return (
    <div className="min-h-screen flex flex-col">
      <Header />

      <main className="flex-1 flex flex-col max-w-6xl mx-auto w-full px-4 py-4 gap-4 min-h-0">
        {/* Back + Property header */}
        <div className="flex items-start gap-3">
          <button
            onClick={() => navigate('/')}
            className="btn-secondary p-2 mt-0.5 flex-shrink-0"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h1 className="text-lg font-bold text-slate-900 leading-tight">
                  {property.property_name}
                </h1>
                <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-slate-500">
                  {property.survey_number && (
                    <span className="flex items-center gap-1">
                      <Info className="w-3 h-3" /> Sy. No. {property.survey_number}
                    </span>
                  )}
                  {(property.village || property.taluk) && (
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {[property.village, property.hobli, property.taluk].filter(Boolean).join(', ')}
                    </span>
                  )}
                  {property.total_area && (
                    <span>Area: {property.total_area}</span>
                  )}
                </div>
              </div>

              {/* Status indicators */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {polling && (
                  <div className="flex items-center gap-1.5 text-xs text-brand-600">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    Processing...
                  </div>
                )}
                <span className="badge bg-slate-100 text-slate-600">
                  {readyCount}/{documents.length} ready
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-200">
          {TABS.map(t => {
            const Icon = t.icon
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                  ${tab === t.id
                    ? 'border-brand-600 text-brand-700'
                    : 'border-transparent text-slate-500 hover:text-slate-700'}`}
              >
                <Icon className="w-4 h-4" />
                {t.label}
                {t.id === 'documents' && documents.length > 0 && (
                  <span className="badge bg-slate-200 text-slate-600 ml-0.5">{documents.length}</span>
                )}
                {t.id === 'report' && reports.length > 0 && (
                  <span className="badge bg-slate-200 text-slate-600 ml-0.5">{reports.length}</span>
                )}
              </button>
            )
          })}
        </div>

        {/* Tab content */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {tab === 'documents' && (
            <div className="space-y-4 pb-4">
              <div className="card p-4">
                <h2 className="font-semibold text-slate-800 text-sm mb-3">Upload Documents</h2>
                <DocumentUpload propertyId={id} onUploaded={handleUploaded} />
              </div>
              <div className="card p-4">
                <h2 className="font-semibold text-slate-800 text-sm mb-3">Document Library</h2>
                <DocumentList
                  documents={documents}
                  propertyId={id}
                  onDeleted={handleDeleted}
                  onTypeChanged={handleTypeChanged}
                />
              </div>
            </div>
          )}

          {tab === 'query' && (
            <div className="card h-[calc(100vh-280px)] flex flex-col overflow-hidden">
              {readyCount === 0 ? (
                <div className="flex-1 flex items-center justify-center text-center p-8">
                  <div>
                    <FileText className="w-10 h-10 mx-auto text-slate-300 mb-3" />
                    <p className="text-slate-500 font-medium">No documents processed yet</p>
                    <p className="text-slate-400 text-sm mt-1">
                      Upload documents and wait for processing to complete
                    </p>
                  </div>
                </div>
              ) : (
                <QueryInterface propertyId={id} />
              )}
            </div>
          )}

          {tab === 'report' && (
            <div className="card p-4 pb-8">
              <ReportView
                propertyId={id}
                existingReports={reports}
                onGenerated={handleReportGenerated}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
