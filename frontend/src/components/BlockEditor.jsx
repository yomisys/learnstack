import AddIcon from '@mui/icons-material/Add'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import DeleteIcon from '@mui/icons-material/Delete'
import {
  Alert, Box, Button, Card, CardContent, Chip, IconButton, MenuItem, Stack,
  TextField, Typography,
} from '@mui/material'
import { useState } from 'react'
import { api, errText } from '../api'

const NEW_BLOCK = {
  text: { body: '' },
  video: { provider: 'youtube', url: '', caption: '' },
  audio: { url: '', caption: '' },
  image: { url: '', alt: '', caption: '' },
  file: { url: '', name: '' },
  embed: { url: '' },
  quiz: { pass_score: 0, questions: [{ question: '', options: ['', ''], correct: 0 }] },
}

function UploadButton({ accept, onUploaded }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  return (
    <Box>
      <Button component="label" size="small" variant="outlined" disabled={busy}>
        {busy ? 'Uploading…' : 'Upload file'}
        <input
          hidden type="file" accept={accept}
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            setBusy(true)
            setError('')
            const form = new FormData()
            form.append('file', file)
            try {
              const r = await api.post('/api/media/upload', form)
              onUploaded(r.data)
            } catch (err) {
              setError(errText(err))
            } finally {
              setBusy(false)
            }
          }}
        />
      </Button>
      {error && <Alert severity="error" sx={{ mt: 1 }}>{error}</Alert>}
    </Box>
  )
}

function QuizFields({ data, update }) {
  const questions = data.questions || []
  const setQ = (qi, patch) => {
    const next = questions.map((q, i) => (i === qi ? { ...q, ...patch } : q))
    update({ questions: next })
  }
  return (
    <Stack spacing={2}>
      <TextField
        label="Pass score (%)" type="number" size="small" sx={{ width: 160 }}
        value={data.pass_score ?? 0}
        onChange={(e) => update({ pass_score: Number(e.target.value) })}
      />
      {questions.map((q, qi) => (
        <Card key={qi} variant="outlined" sx={{ p: 1.5 }}>
          <Stack spacing={1}>
            <Stack direction="row" spacing={1} alignItems="center">
              <TextField
                fullWidth size="small" label={`Question ${qi + 1}`} value={q.question}
                onChange={(e) => setQ(qi, { question: e.target.value })}
              />
              <IconButton onClick={() => update({ questions: questions.filter((_, i) => i !== qi) })}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
            {q.options.map((opt, oi) => (
              <Stack key={oi} direction="row" spacing={1} alignItems="center">
                <Chip
                  size="small" label={q.correct === oi ? 'correct' : 'mark correct'}
                  color={q.correct === oi ? 'success' : 'default'}
                  onClick={() => setQ(qi, { correct: oi })}
                />
                <TextField
                  fullWidth size="small" label={`Option ${oi + 1}`} value={opt}
                  onChange={(e) =>
                    setQ(qi, { options: q.options.map((o, i) => (i === oi ? e.target.value : o)) })}
                />
                <IconButton
                  disabled={q.options.length <= 2}
                  onClick={() => {
                    const options = q.options.filter((_, i) => i !== oi)
                    setQ(qi, { options, correct: Math.min(q.correct, options.length - 1) })
                  }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Stack>
            ))}
            <Button size="small" onClick={() => setQ(qi, { options: [...q.options, ''] })}>
              Add option
            </Button>
          </Stack>
        </Card>
      ))}
      <Button
        size="small" startIcon={<AddIcon />}
        onClick={() => update({
          questions: [...questions, { question: '', options: ['', ''], correct: 0 }],
        })}
      >
        Add question
      </Button>
    </Stack>
  )
}

function BlockFields({ block, update }) {
  const d = block.data
  switch (block.type) {
    case 'text':
      return (
        <TextField
          fullWidth multiline minRows={4} label="Markdown content" value={d.body}
          onChange={(e) => update({ body: e.target.value })}
        />
      )
    case 'video':
      return (
        <Stack spacing={1}>
          <TextField
            select size="small" label="Source" value={d.provider || 'youtube'} sx={{ width: 200 }}
            onChange={(e) => update({ provider: e.target.value })}
          >
            <MenuItem value="youtube">YouTube</MenuItem>
            <MenuItem value="vimeo">Vimeo</MenuItem>
            <MenuItem value="upload">Uploaded / direct file</MenuItem>
          </TextField>
          <TextField
            fullWidth size="small" label="Video URL" value={d.url}
            onChange={(e) => update({ url: e.target.value })}
          />
          {d.provider === 'upload' && (
            <UploadButton accept="video/*" onUploaded={(m) => update({ url: m.url })} />
          )}
          <TextField
            fullWidth size="small" label="Caption" value={d.caption || ''}
            onChange={(e) => update({ caption: e.target.value })}
          />
        </Stack>
      )
    case 'audio':
    case 'image':
    case 'file': {
      const accept = block.type === 'audio' ? 'audio/*' : block.type === 'image' ? 'image/*' : undefined
      return (
        <Stack spacing={1}>
          <TextField
            fullWidth size="small" label="URL" value={d.url}
            onChange={(e) => update({ url: e.target.value })}
          />
          <UploadButton
            accept={accept}
            onUploaded={(m) => update({ url: m.url, ...(block.type === 'file' ? { name: m.filename } : {}) })}
          />
          {block.type === 'file' ? (
            <TextField fullWidth size="small" label="Display name" value={d.name || ''}
              onChange={(e) => update({ name: e.target.value })} />
          ) : (
            <TextField fullWidth size="small" label="Caption" value={d.caption || ''}
              onChange={(e) => update({ caption: e.target.value })} />
          )}
        </Stack>
      )
    }
    case 'embed':
      return (
        <TextField
          fullWidth size="small" label="Embed URL (iframe src)" value={d.url || ''}
          onChange={(e) => update({ url: e.target.value })}
        />
      )
    case 'quiz':
      return <QuizFields data={d} update={update} />
    default:
      return null
  }
}

export default function BlockEditor({ blocks, onChange }) {
  const setBlock = (i, patch) =>
    onChange(blocks.map((b, idx) => (idx === i ? { ...b, data: { ...b.data, ...patch } } : b)))
  const move = (i, dir) => {
    const j = i + dir
    if (j < 0 || j >= blocks.length) return
    const next = [...blocks]
    ;[next[i], next[j]] = [next[j], next[i]]
    onChange(next)
  }
  return (
    <Stack spacing={2}>
      {blocks.map((block, i) => (
        <Card key={i} variant="outlined">
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
              <Typography variant="overline">{block.type}</Typography>
              <Box>
                <IconButton size="small" onClick={() => move(i, -1)}><ArrowUpwardIcon fontSize="small" /></IconButton>
                <IconButton size="small" onClick={() => move(i, 1)}><ArrowDownwardIcon fontSize="small" /></IconButton>
                <IconButton size="small" onClick={() => onChange(blocks.filter((_, idx) => idx !== i))}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            </Stack>
            <BlockFields block={block} update={(patch) => setBlock(i, patch)} />
          </CardContent>
        </Card>
      ))}
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {Object.keys(NEW_BLOCK).map((type) => (
          <Button
            key={type} size="small" variant="outlined" startIcon={<AddIcon />}
            onClick={() => onChange([...blocks, { type, data: structuredClone(NEW_BLOCK[type]) }])}
          >
            {type}
          </Button>
        ))}
      </Stack>
    </Stack>
  )
}
