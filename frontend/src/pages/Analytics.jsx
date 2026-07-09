import DownloadIcon from '@mui/icons-material/Download'
import {
  Alert, Box, Card, CardContent, Chip, Container, Grid, MenuItem,
  Stack, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  TextField, Typography, Button,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { api, errText } from '../api'

function StatCard({ label, value, sub }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="body2" color="text.secondary" gutterBottom>{label}</Typography>
        <Typography variant="h4" fontWeight={700}>{value}</Typography>
        {sub && <Typography variant="caption" color="text.secondary">{sub}</Typography>}
      </CardContent>
    </Card>
  )
}

function toCsv(rows) {
  const headers = ['Name', 'Email', 'Curriculum', 'Enrolled', 'Completed', 'Lessons Done', 'Lessons Total']
  const lines = rows.map((r) => [
    r.full_name, r.email, r.curriculum_title,
    new Date(r.enrolled_at).toLocaleDateString(),
    r.completed_at ? new Date(r.completed_at).toLocaleDateString() : '',
    r.lessons_completed, r.lessons_total,
  ].map((v) => `"${String(v).replace(/"/g, '""')}"`).join(','))
  return [headers.join(','), ...lines].join('\n')
}

function downloadCsv(csv, filename) {
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function Analytics() {
  const [summary, setSummary] = useState(null)
  const [roster, setRoster] = useState([])
  const [curriculumFilter, setCurriculumFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/api/analytics/summary').then((r) => setSummary(r.data)).catch((e) => setError(errText(e)))
  }, [])

  useEffect(() => {
    const params = curriculumFilter ? { curriculum_id: curriculumFilter } : {}
    api.get('/api/analytics/learners', { params })
      .then((r) => setRoster(r.data))
      .catch((e) => setError(errText(e)))
  }, [curriculumFilter])

  const emptyState = summary && summary.total_enrollments === 0

  const exportRoster = () => downloadCsv(toCsv(roster), 'learners.csv')

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Analytics</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Who signed up and who finished, for your organization only.
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 3 }}>{error}</Alert>}

      {summary && (
        <Grid container spacing={2} sx={{ mb: 4 }}>
          <Grid item xs={6} sm={3}>
            <StatCard label="People enrolled" value={summary.total_learners} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Total enrollments" value={summary.total_enrollments}
              sub="across all your curricula" />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Completed" value={summary.completed_enrollments} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <StatCard label="Completion rate" value={`${summary.completion_rate}%`} />
          </Grid>
        </Grid>
      )}

      {emptyState && (
        <Alert severity="info" sx={{ mb: 4 }}>
          Nobody has enrolled yet. Once people start joining via your signup link
          or messaging channel, their progress shows up here.
        </Alert>
      )}

      {summary && summary.by_curriculum.length > 0 && (
        <Card variant="outlined" sx={{ mb: 4 }}>
          <CardContent>
            <Typography variant="h6" fontWeight={700} gutterBottom>By curriculum</Typography>
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Curriculum</TableCell>
                    <TableCell align="right">Enrolled</TableCell>
                    <TableCell align="right">Completed</TableCell>
                    <TableCell align="right">Rate</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {summary.by_curriculum.map((c) => (
                    <TableRow key={c.curriculum_id}>
                      <TableCell>{c.curriculum_title}</TableCell>
                      <TableCell align="right">{c.enrolled}</TableCell>
                      <TableCell align="right">{c.completed}</TableCell>
                      <TableCell align="right">{c.completion_rate}%</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}

      {!emptyState && (
        <Card variant="outlined">
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center"
              flexWrap="wrap" gap={2} sx={{ mb: 2 }}>
              <Typography variant="h6" fontWeight={700}>Learners</Typography>
              <Stack direction="row" spacing={2} alignItems="center">
                {summary && summary.by_curriculum.length > 1 && (
                  <TextField select size="small" label="Curriculum" sx={{ minWidth: 200 }}
                    value={curriculumFilter} onChange={(e) => setCurriculumFilter(e.target.value)}>
                    <MenuItem value="">All curricula</MenuItem>
                    {summary.by_curriculum.map((c) => (
                      <MenuItem key={c.curriculum_id} value={c.curriculum_id}>{c.curriculum_title}</MenuItem>
                    ))}
                  </TextField>
                )}
                <Button startIcon={<DownloadIcon />} onClick={exportRoster} disabled={!roster.length}>
                  Export CSV
                </Button>
              </Stack>
            </Stack>
            <TableContainer sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>Email</TableCell>
                    <TableCell>Curriculum</TableCell>
                    <TableCell align="right">Progress</TableCell>
                    <TableCell>Status</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {roster.map((r, i) => (
                    <TableRow key={`${r.user_id}-${r.curriculum_id}-${i}`}>
                      <TableCell>{r.full_name}</TableCell>
                      <TableCell>{r.email}</TableCell>
                      <TableCell>{r.curriculum_title}</TableCell>
                      <TableCell align="right">{r.lessons_completed}/{r.lessons_total}</TableCell>
                      <TableCell>
                        <Chip size="small"
                          label={r.completed_at ? 'Completed' : 'In progress'}
                          color={r.completed_at ? 'success' : 'default'} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </CardContent>
        </Card>
      )}
    </Container>
  )
}
