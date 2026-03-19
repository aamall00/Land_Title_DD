import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../../lib/api'
import { RefreshCw, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

// ── Colour palette by entity type ────────────────────────────────────────────
const TYPE_COLORS = {
  OWNER:       '#6366f1',  // indigo
  PERSON:      '#6366f1',
  SURVEY_NO:   '#0ea5e9',  // sky
  AREA:        '#10b981',  // emerald
  DATE:        '#f59e0b',  // amber
  MONEY:       '#ef4444',  // red
  AMOUNT:      '#ef4444',
  KHATA:       '#8b5cf6',  // violet
  DOCUMENT:    '#64748b',  // slate
  COURT:       '#dc2626',
  BANK:        '#0891b2',
  DEFAULT:     '#94a3b8',
}

function nodeColor(type) {
  return TYPE_COLORS[type?.toUpperCase()] ?? TYPE_COLORS.DEFAULT
}

// ── Force-directed simulation (vanilla, no d3) ───────────────────────────────
function createSimulation(nodes, links, width, height) {
  const NODE_REPULSION = 3000
  const LINK_STRENGTH  = 0.08
  const LINK_DIST      = 120
  const DAMPING        = 0.85
  const CENTER_PULL    = 0.02

  // Assign initial positions in a circle
  nodes.forEach((n, i) => {
    const angle = (i / nodes.length) * 2 * Math.PI
    const r = Math.min(width, height) * 0.3
    n.x  ??= width  / 2 + r * Math.cos(angle)
    n.y  ??= height / 2 + r * Math.sin(angle)
    n.vx ??= 0
    n.vy ??= 0
  })

  const nodeById = Object.fromEntries(nodes.map(n => [n.id, n]))

  function tick() {
    // Repulsion between all pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i], b = nodes[j]
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist2 = dx * dx + dy * dy + 1
        const force = NODE_REPULSION / dist2
        const fx = force * dx / Math.sqrt(dist2)
        const fy = force * dy / Math.sqrt(dist2)
        a.vx -= fx; a.vy -= fy
        b.vx += fx; b.vy += fy
      }
    }

    // Attraction along links
    for (const link of links) {
      const a = nodeById[link.source]
      const b = nodeById[link.target]
      if (!a || !b) continue
      const dx = b.x - a.x
      const dy = b.y - a.y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = (dist - LINK_DIST) * LINK_STRENGTH
      const fx = force * dx / dist
      const fy = force * dy / dist
      a.vx += fx; a.vy += fy
      b.vx -= fx; b.vy -= fy
    }

    // Centre-gravity pull
    for (const n of nodes) {
      n.vx += (width  / 2 - n.x) * CENTER_PULL
      n.vy += (height / 2 - n.y) * CENTER_PULL
    }

    // Integrate + dampen
    for (const n of nodes) {
      n.vx *= DAMPING
      n.vy *= DAMPING
      n.x  += n.vx
      n.y  += n.vy
    }
  }

  return { tick, nodes, nodeById }
}

// ── Canvas renderer ───────────────────────────────────────────────────────────
function drawGraph(ctx, nodes, links, nodeById, transform, hoveredId) {
  const { tx, ty, scale } = transform
  ctx.save()
  ctx.translate(tx, ty)
  ctx.scale(scale, scale)

  // Draw links
  ctx.lineWidth = 1.5
  for (const link of links) {
    const a = nodeById[link.source]
    const b = nodeById[link.target]
    if (!a || !b) continue

    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    // Shorten line so it doesn't overlap nodes
    const r = 14
    const x1 = a.x + (dx / dist) * r
    const y1 = a.y + (dy / dist) * r
    const x2 = b.x - (dx / dist) * (r + 6)
    const y2 = b.y - (dy / dist) * (r + 6)

    ctx.strokeStyle = 'rgba(148,163,184,0.6)'
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()

    // Arrowhead
    const angle = Math.atan2(y2 - y1, x2 - x1)
    ctx.fillStyle = 'rgba(148,163,184,0.6)'
    ctx.beginPath()
    ctx.moveTo(x2, y2)
    ctx.lineTo(x2 - 8 * Math.cos(angle - 0.4), y2 - 8 * Math.sin(angle - 0.4))
    ctx.lineTo(x2 - 8 * Math.cos(angle + 0.4), y2 - 8 * Math.sin(angle + 0.4))
    ctx.closePath()
    ctx.fill()

    // Edge label (mid-point)
    if (link.label) {
      const mx = (x1 + x2) / 2
      const my = (y1 + y2) / 2
      ctx.font = '8px sans-serif'
      ctx.fillStyle = '#64748b'
      ctx.textAlign = 'center'
      ctx.fillText(link.label.replace(/_/g, ' '), mx, my - 4)
    }
  }

  // Draw nodes
  for (const node of nodes) {
    const r = 14 + Math.min(node.doc_count - 1, 4) * 2
    const color = nodeColor(node.type)
    const isHovered = node.id === hoveredId

    ctx.beginPath()
    ctx.arc(node.x, node.y, r + (isHovered ? 3 : 0), 0, 2 * Math.PI)
    ctx.fillStyle = isHovered ? color : color + 'cc'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 2
    ctx.stroke()

    if (node.doc_count > 1) {
      ctx.font = `bold ${8}px sans-serif`
      ctx.fillStyle = '#fff'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(node.doc_count, node.x, node.y)
    }

    // Label below node
    const maxLen = 16
    const label = node.name.length > maxLen
      ? node.name.slice(0, maxLen) + '…'
      : node.name
    ctx.font = isHovered ? 'bold 10px sans-serif' : '9px sans-serif'
    ctx.fillStyle = '#1e293b'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText(label, node.x, node.y + r + 4)

    // Type badge (tiny)
    ctx.font = '7px sans-serif'
    ctx.fillStyle = color
    ctx.fillText(node.type, node.x, node.y + r + 15)
  }

  ctx.restore()
}

// ── Main component ────────────────────────────────────────────────────────────
export default function KnowledgeGraph({ propertyId }) {
  const [graphData, setGraphData]   = useState(null)
  const [loading,   setLoading]     = useState(true)
  const [error,     setError]       = useState('')
  const [hovered,   setHovered]     = useState(null)
  const [tooltip,   setTooltip]     = useState(null)

  const canvasRef  = useRef(null)
  const simRef     = useRef(null)
  const rafRef     = useRef(null)
  const dragRef    = useRef(null)
  const transformRef = useRef({ tx: 0, ty: 0, scale: 1 })

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await api.graph.get(propertyId)
      setGraphData(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [propertyId])

  // ── Simulation + render loop ────────────────────────────────────────────
  useEffect(() => {
    if (!graphData || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx    = canvas.getContext('2d')

    const W = canvas.offsetWidth  || 800
    const H = canvas.offsetHeight || 500
    canvas.width  = W
    canvas.height = H

    // Deep-copy nodes so positions are stable across re-renders
    const nodes = graphData.nodes.map(n => ({ ...n }))
    const links = graphData.links

    simRef.current = createSimulation(nodes, links, W, H)
    const { tick, nodeById } = simRef.current

    let frame = 0
    function loop() {
      if (frame < 300) { tick(); frame++ }
      ctx.clearRect(0, 0, W, H)
      drawGraph(ctx, nodes, links, nodeById, transformRef.current, hovered)
      rafRef.current = requestAnimationFrame(loop)
    }
    rafRef.current = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(rafRef.current)
    }
  }, [graphData])

  // Re-draw on hover change without restarting sim
  useEffect(() => {
    if (!simRef.current || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx    = canvas.getContext('2d')
    const { nodes, nodeById } = simRef.current
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    drawGraph(ctx, nodes, graphData?.links ?? [], nodeById, transformRef.current, hovered)
  }, [hovered])

  // ── Pointer interactions ────────────────────────────────────────────────
  function worldPos(e) {
    const rect = canvasRef.current.getBoundingClientRect()
    const { tx, ty, scale } = transformRef.current
    return {
      wx: (e.clientX - rect.left - tx) / scale,
      wy: (e.clientY - rect.top  - ty) / scale,
    }
  }

  function hitTest(wx, wy) {
    if (!simRef.current) return null
    for (const n of simRef.current.nodes) {
      const r = 14 + Math.min((n.doc_count ?? 1) - 1, 4) * 2 + 4
      const dx = n.x - wx, dy = n.y - wy
      if (dx * dx + dy * dy < r * r) return n
    }
    return null
  }

  const onMouseMove = useCallback((e) => {
    const { wx, wy } = worldPos(e)

    // Panning
    if (dragRef.current?.type === 'pan') {
      transformRef.current.tx += e.movementX
      transformRef.current.ty += e.movementY
      return
    }
    // Node drag
    if (dragRef.current?.type === 'node') {
      dragRef.current.node.x = wx
      dragRef.current.node.y = wy
      dragRef.current.node.vx = 0
      dragRef.current.node.vy = 0
      return
    }

    const hit = hitTest(wx, wy)
    setHovered(hit?.id ?? null)
    if (hit) {
      const rect = canvasRef.current.getBoundingClientRect()
      setTooltip({ node: hit, x: e.clientX - rect.left, y: e.clientY - rect.top })
    } else {
      setTooltip(null)
    }
  }, [])

  const onMouseDown = useCallback((e) => {
    const { wx, wy } = worldPos(e)
    const hit = hitTest(wx, wy)
    if (hit) {
      dragRef.current = { type: 'node', node: hit }
    } else {
      dragRef.current = { type: 'pan' }
    }
  }, [])

  const onMouseUp = useCallback(() => { dragRef.current = null }, [])

  const onWheel = useCallback((e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    const rect = canvasRef.current.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const t  = transformRef.current
    t.tx = mx - delta * (mx - t.tx)
    t.ty = my - delta * (my - t.ty)
    t.scale = Math.min(4, Math.max(0.2, t.scale * delta))
  }, [])

  function zoomBy(factor) {
    const canvas = canvasRef.current
    const t = transformRef.current
    const mx = canvas.width  / 2
    const my = canvas.height / 2
    t.tx = mx - factor * (mx - t.tx)
    t.ty = my - factor * (my - t.ty)
    t.scale = Math.min(4, Math.max(0.2, t.scale * factor))
  }

  function resetView() {
    transformRef.current = { tx: 0, ty: 0, scale: 1 }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-500">
      <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-600 border-t-transparent mr-3" />
      Building knowledge graph…
    </div>
  )

  if (error) return (
    <div className="flex items-center justify-center h-64 text-red-500 text-sm">
      {error}
    </div>
  )

  if (!graphData?.nodes?.length) return (
    <div className="flex flex-col items-center justify-center h-64 text-slate-400 text-sm gap-2">
      <span className="text-3xl">🕸️</span>
      <p>No entities extracted yet.</p>
      <p className="text-xs">Upload and process documents to populate the knowledge graph.</p>
    </div>
  )

  const { nodes, links } = graphData

  // Legend: unique types
  const types = [...new Set(nodes.map(n => n.type))]

  return (
    <div className="flex flex-col gap-3">
      {/* Stats + controls */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <span><strong className="text-slate-700">{nodes.length}</strong> entities</span>
          <span><strong className="text-slate-700">{links.length}</strong> relationships</span>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={() => zoomBy(1.2)} className="btn-secondary p-1.5" title="Zoom in">
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button onClick={() => zoomBy(0.8)} className="btn-secondary p-1.5" title="Zoom out">
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <button onClick={resetView} className="btn-secondary p-1.5" title="Reset view">
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
          <button onClick={load} className="btn-secondary p-1.5" title="Refresh">
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-2">
        {types.map(t => (
          <span key={t} className="flex items-center gap-1 text-xs text-slate-600">
            <span
              className="inline-block w-2.5 h-2.5 rounded-full"
              style={{ background: nodeColor(t) }}
            />
            {t}
          </span>
        ))}
      </div>

      {/* Canvas */}
      <div className="relative rounded-lg border border-slate-200 overflow-hidden bg-slate-50" style={{ height: 520 }}>
        <canvas
          ref={canvasRef}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          onMouseMove={onMouseMove}
          onMouseDown={onMouseDown}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
          onWheel={onWheel}
        />

        {/* Hover tooltip */}
        {tooltip && (
          <div
            className="absolute pointer-events-none bg-white border border-slate-200 rounded shadow-lg text-xs p-2 max-w-xs"
            style={{ left: tooltip.x + 12, top: tooltip.y - 8 }}
          >
            <div className="font-semibold text-slate-800">{tooltip.node.name}</div>
            <div className="text-slate-500 mt-0.5">
              Type: <span style={{ color: nodeColor(tooltip.node.type) }}>{tooltip.node.type}</span>
            </div>
            {tooltip.node.doc_count > 1 && (
              <div className="text-slate-500">Seen in {tooltip.node.doc_count} documents</div>
            )}
          </div>
        )}

        <p className="absolute bottom-2 right-3 text-xs text-slate-400 pointer-events-none">
          Scroll to zoom · Drag to pan · Drag nodes to reposition
        </p>
      </div>
    </div>
  )
}
