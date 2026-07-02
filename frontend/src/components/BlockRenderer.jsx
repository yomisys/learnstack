import {
  Alert, Box, Button, Card, CardContent, FormControlLabel, Link, Radio,
  RadioGroup, Typography,
} from '@mui/material'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useState } from 'react'
import { api, errText } from '../api'

function Markdown({ body }) {
  const html = DOMPurify.sanitize(marked.parse(body || ''))
  return <Box sx={{ '& img': { maxWidth: '100%' } }} dangerouslySetInnerHTML={{ __html: html }} />
}

function youTubeId(url) {
  const m = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/)
  return m ? m[1] : null
}

function VideoBlock({ data }) {
  const { url = '', provider = 'upload', caption = '' } = data
  let player
  const yt = provider === 'youtube' || youTubeId(url) ? youTubeId(url) : null
  if (yt) {
    player = (
      <Box sx={{ position: 'relative', pt: '56.25%' }}>
        <iframe
          src={`https://www.youtube.com/embed/${yt}`}
          title={caption || 'video'}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }}
          allowFullScreen
        />
      </Box>
    )
  } else if (provider === 'vimeo' || url.includes('vimeo.com')) {
    const id = url.match(/vimeo\.com\/(\d+)/)?.[1]
    player = id ? (
      <Box sx={{ position: 'relative', pt: '56.25%' }}>
        <iframe
          src={`https://player.vimeo.com/video/${id}`}
          title={caption || 'video'}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }}
          allowFullScreen
        />
      </Box>
    ) : <Alert severity="warning">Invalid Vimeo URL</Alert>
  } else {
    player = <video src={url} controls style={{ width: '100%', borderRadius: 8 }} />
  }
  return (
    <Box>
      {player}
      {caption && <Typography variant="caption" color="text.secondary">{caption}</Typography>}
    </Box>
  )
}

function QuizBlock({ data, lessonId, blockIndex, onGraded }) {
  const questions = data.questions || []
  const [answers, setAnswers] = useState(Array(questions.length).fill(-1))
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  const submit = async () => {
    setError('')
    try {
      const r = await api.post(`/api/learn/lessons/${lessonId}/quiz`, {
        block_index: blockIndex,
        answers,
      })
      setResult(r.data)
      onGraded?.(r.data)
    } catch (e) {
      setError(errText(e))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>Quiz</Typography>
        {questions.map((q, qi) => (
          <Box key={qi} sx={{ mb: 2 }}>
            <Typography fontWeight={600}>{qi + 1}. {q.question}</Typography>
            <RadioGroup
              value={answers[qi]}
              onChange={(e) => {
                const next = [...answers]
                next[qi] = Number(e.target.value)
                setAnswers(next)
              }}
            >
              {(q.options || []).map((opt, oi) => (
                <FormControlLabel
                  key={oi} value={oi} control={<Radio size="small" />} label={opt}
                  sx={result && result.correct_answers[qi] === oi
                    ? { color: 'success.main' } : undefined}
                />
              ))}
            </RadioGroup>
          </Box>
        ))}
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
        {result ? (
          <Alert severity={result.passed ? 'success' : 'warning'}>
            Score: {result.score}/{result.total} {result.passed ? '— passed!' : '— try reviewing the lesson again.'}
          </Alert>
        ) : (
          <Button variant="contained" onClick={submit} disabled={answers.includes(-1)}>
            Submit answers
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

export default function BlockRenderer({ block, index, lessonId, onQuizGraded }) {
  const { type, data = {} } = block
  switch (type) {
    case 'text':
      return <Markdown body={data.body} />
    case 'video':
      return <VideoBlock data={data} />
    case 'audio':
      return (
        <Box>
          <audio src={data.url} controls style={{ width: '100%' }} />
          {data.caption && <Typography variant="caption" color="text.secondary">{data.caption}</Typography>}
        </Box>
      )
    case 'image':
      return (
        <Box>
          <img src={data.url} alt={data.alt || ''} style={{ maxWidth: '100%', borderRadius: 8 }} />
          {data.caption && <Typography variant="caption" display="block" color="text.secondary">{data.caption}</Typography>}
        </Box>
      )
    case 'file':
      return <Link href={data.url} target="_blank" rel="noopener">📎 {data.name || 'Download attachment'}</Link>
    case 'embed':
      return data.url ? (
        <Box sx={{ position: 'relative', pt: '56.25%' }}>
          <iframe src={data.url} title="embed"
            style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }} />
        </Box>
      ) : <Markdown body={data.html || ''} />
    case 'quiz':
      return <QuizBlock data={data} lessonId={lessonId} blockIndex={index} onGraded={onQuizGraded} />
    default:
      return <Alert severity="warning">Unsupported block type: {type}</Alert>
  }
}
