import { useState } from 'react'
import {
  ShieldCheck, ShieldAlert, ShieldX, AlertTriangle,
  CheckCircle2, XCircle, AlertCircle, HelpCircle,
  ChevronDown, ChevronUp, FileWarning, ListChecks,
  Loader, RefreshCw
} from 'lucide-react'
import { api } from '../../lib/api'

// ── Risk helpers ───────────────────────────────────────────────
const RISK_CONFIG = {
  LOW:      { icon: ShieldCheck,  cls: 'text-green-600 bg-green-50 border-green-200', label: 'LOW RISK' },
  MEDIUM:   { icon: ShieldAlert,  cls: 'text-amber-600 bg-amber-50 border-amber-200', label: 'MEDIUM RISK' },
  HIGH:     { icon: ShieldAlert,  cls: 'text-red-600 bg-red-50 border-red-200',       label: 'HIGH RISK' },
  CRITICAL: { icon: ShieldX,      cls: 'text-red-900 bg-red-100 border-red-300',      label: 'CRITICAL RISK' },
}

const STATUS_CONFIG = {
  PASS:    { icon: CheckCircle2, cls: 'text-green-600' },
  FAIL:    { icon: XCircle,      cls: 'text-red-600'   },
  WARN:    { icon: AlertCircle,  cls: 'text-amber-600' },
  MISSING: { icon: HelpCircle,   cls: 'text-slate-400' },
}

const CHECK_LABELS = {
  title_chain:       'Title Chain (30-year)',
  encumbrances:      'Encumbrances / Liens',
  litigation:        'Litigation / Court Cases',
  khata_consistency: 'Khata Consistency',
  measurement_match: 'Area & Measurement Match',
  layout_approval:   'Layout / Plan Approval',
}

function CheckCard({ checkKey, result }) {
  const [open, setOpen] = useState(false)
  const statusCfg = STATUS_CONFIG[result.status] || STATUS_CONFIG.WARN
  const Icon = statusCfg.icon

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-3 w-full p-3 bg-white hover:bg-slate-50 text-left"
      >
        <Icon className={`w-4 h-4 flex-shrink-0 ${statusCfg.cls}`} />
        <span className="font-medium text-slate-800 flex-1 text-sm">
          {CHECK_LABELS[checkKey] || checkKey}
        </span>
        <span className={`badge status-${result.status}`}>{result.status}</span>
        {open ? <ChevronUp className="w-3.5 h-3.5 text-slate-400" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-400" />}
      </button>

      {open && (
        <div className="px-4 pb-4 border-t border-slate-100 bg-slate-50 space-y-3 pt-3">
          <p className="text-sm text-slate-700">{result.summary}</p>

          {result.findings?.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase mb-1.5">Findings</p>
              <ul className="space-y-1">
                {result.findings.map((f, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className="text-slate-400 flex-shrink-0">•</span>
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.sources?.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {result.sources.map((s, i) => (
                <span key={i} className="badge bg-slate-100 text-slate-600 text-xs">{s}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ReportView({ propertyId, existingReports = [], onGenerated }) {
  const [generating, setGenerating] = useState(false)
  const [reportType, setReportType] = useState('full_due_diligence')
  const [error, setError] = useState('')
  const [activeReport, setActiveReport] = useState(existingReports[0] ?? null)

  async function handleGenerate() {
    if (!confirm('Generate a new due diligence report? This may take 30–60 seconds.')) return
    setGenerating(true)
    setError('')
    try {
      const report = await api.reports.generate(propertyId, { report_type: reportType })
      setActiveReport(report)
      onGenerated?.(report)
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  const report = activeReport
  const content = report?.content || {}
  const riskCfg = RISK_CONFIG[report?.risk_level] || RISK_CONFIG.MEDIUM
  const RiskIcon = riskCfg.icon

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="input text-sm w-auto"
          value={reportType}
          onChange={e => setReportType(e.target.value)}
        >
          <option value="full_due_diligence">Full Due Diligence</option>
          <option value="title_chain">Title Chain Only</option>
          <option value="risk_summary">Risk Summary</option>
        </select>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-primary"
        >
          {generating
            ? <><Loader className="w-4 h-4 animate-spin" /> Generating...</>
            : <><RefreshCw className="w-4 h-4" /> Generate Report</>}
        </button>

        {existingReports.length > 1 && (
          <select
            className="input text-sm w-auto ml-auto"
            onChange={e => {
              const r = existingReports.find(r => r.id === e.target.value)
              if (r) setActiveReport(r)
            }}
            value={activeReport?.id || ''}
          >
            {existingReports.map(r => (
              <option key={r.id} value={r.id}>
                {new Date(r.generated_at).toLocaleString('en-IN')} — {r.report_type}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          {error}
        </div>
      )}

      {!report && !generating && (
        <div className="text-center text-slate-400 text-sm py-12">
          <ListChecks className="w-10 h-10 mx-auto mb-2 text-slate-300" />
          No report generated yet. Click "Generate Report" to start analysis.
        </div>
      )}

      {report && (
        <div className="space-y-4">
          {/* Risk banner */}
          <div className={`flex items-center gap-4 p-4 rounded-xl border ${riskCfg.cls}`}>
            <RiskIcon className="w-8 h-8 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg">{riskCfg.label}</span>
                {report.risk_score != null && (
                  <span className="text-sm opacity-70">Score: {report.risk_score}/100</span>
                )}
              </div>
              {content.summary && (
                <p className="text-sm mt-0.5 opacity-80">{content.summary}</p>
              )}
            </div>
            <div className="text-xs opacity-60 text-right">
              {new Date(report.generated_at).toLocaleString('en-IN', {
                day: '2-digit', month: 'short', year: 'numeric',
                hour: '2-digit', minute: '2-digit',
              })}
            </div>
          </div>

          {/* Red flags */}
          {content.red_flags?.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileWarning className="w-4 h-4 text-red-600" />
                <span className="font-semibold text-red-700 text-sm">
                  Red Flags ({content.red_flags.length})
                </span>
              </div>
              <ul className="space-y-1.5">
                {content.red_flags.map((flag, i) => (
                  <li key={i} className="flex gap-2 text-sm text-red-700">
                    <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
                    {flag}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Per-check results */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Detailed Checks</h3>
            <div className="space-y-2">
              {Object.entries(CHECK_LABELS).map(([key]) => {
                const result = content[key]
                if (!result) return null
                return <CheckCard key={key} checkKey={key} result={result} />
              })}
            </div>
          </div>

          {/* Missing documents */}
          {content.missing_documents?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertCircle className="w-4 h-4 text-amber-600" />
                <span className="font-semibold text-amber-700 text-sm">
                  Missing Documents ({content.missing_documents.length})
                </span>
              </div>
              <ul className="space-y-1">
                {content.missing_documents.map((doc, i) => (
                  <li key={i} className="flex gap-2 text-sm text-amber-700">
                    <span className="text-amber-400">•</span>
                    {doc}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
