import {
  Alert, Box, Button, Container, LinearProgress, Stack, Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, errText } from '../api'
import BlockRenderer from '../components/BlockRenderer'

export default function LessonPlayer() {
  const { id } = useParams()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [courseDone, setCourseDone] = useState(false)

  useEffect(() => {
    setLesson(null)
    setDone(false)
    api.get(`/api/learn/lessons/${id}`)
      .then((r) => setLesson(r.data))
      .catch((e) => setError(errText(e)))
  }, [id])

  const complete = async () => {
    try {
      const r = await api.post(`/api/learn/lessons/${id}/complete`)
      setDone(true)
      setCourseDone(r.data.curriculum_completed)
    } catch (e) {
      setError(errText(e))
    }
  }

  if (error) return <Container sx={{ py: 4 }}><Alert severity="error">{error}</Alert></Container>
  if (!lesson) return <Container sx={{ py: 4 }}><LinearProgress /></Container>

  const hasQuiz = lesson.blocks.some((b) => b.type === 'quiz')

  return (
    <Container sx={{ py: 4, maxWidth: 800 }}>
      <Button component={Link} to={`/course/${lesson.curriculum_id}`} size="small">
        ← Back to course
      </Button>
      <Typography variant="h4" fontWeight={700} sx={{ mt: 1 }}>{lesson.title}</Typography>
      {lesson.summary && (
        <Typography color="text.secondary" sx={{ mt: 0.5 }}>{lesson.summary}</Typography>
      )}
      <Stack spacing={3} sx={{ mt: 3 }}>
        {lesson.blocks.map((block, i) => (
          <BlockRenderer
            key={i} block={block} index={i} lessonId={lesson.id}
            onQuizGraded={() => { setDone(true) }}
          />
        ))}
      </Stack>
      <Box sx={{ mt: 4 }}>
        {done ? (
          <Alert severity="success">
            Lesson completed{courseDone ? ' — course finished! Check My learning for your certificate.' : '.'}
          </Alert>
        ) : hasQuiz ? (
          <Typography variant="body2" color="text.secondary">
            Submit the quiz above to complete this lesson.
          </Typography>
        ) : (
          <Button variant="contained" size="large" onClick={complete}>
            Mark lesson complete
          </Button>
        )}
      </Box>
    </Container>
  )
}
