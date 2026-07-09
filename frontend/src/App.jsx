import { Box, Container, Typography } from '@mui/material'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { useBranding } from './branding'
import NavBar from './components/NavBar'
import Admin from './pages/Admin'
import Analytics from './pages/Analytics'
import Catalog from './pages/Catalog'
import Channels from './pages/Channels'
import Course from './pages/Course'
import CurriculumEditor from './pages/CurriculumEditor'
import LessonEditor from './pages/LessonEditor'
import LessonPlayer from './pages/LessonPlayer'
import Login from './pages/Login'
import MyLearning from './pages/MyLearning'
import Verify from './pages/Verify'

function RequireAuth({ children, author = false, manager = false }) {
  const { user, loading, canAuthor, canManageTenant } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (author && !canAuthor) return <Navigate to="/" replace />
  if (manager && !canManageTenant) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const branding = useBranding()
  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <NavBar />
      <Box sx={{ flexGrow: 1 }}>
        <Routes>
          <Route path="/" element={<Catalog />} />
          <Route path="/login" element={<Login />} />
          <Route path="/course/:id" element={<Course />} />
          <Route path="/verify" element={<Verify />} />
          <Route path="/lesson/:id" element={<RequireAuth><LessonPlayer /></RequireAuth>} />
          <Route path="/my" element={<RequireAuth><MyLearning /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth author><Admin /></RequireAuth>} />
          <Route path="/admin/analytics" element={<RequireAuth manager><Analytics /></RequireAuth>} />
          <Route path="/admin/channels" element={<RequireAuth author><Channels /></RequireAuth>} />
          <Route path="/admin/curriculum/:id" element={<RequireAuth author><CurriculumEditor /></RequireAuth>} />
          <Route path="/admin/lesson/:id" element={<RequireAuth author><LessonEditor /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Box>
      <Box component="footer" sx={{ py: 3, bgcolor: 'grey.100', mt: 6 }}>
        <Container>
          <Typography variant="body2" color="text.secondary" align="center">
            {branding.footer_text || `© ${new Date().getFullYear()} ${branding.product_name}`}
            {branding.support_email && ` · ${branding.support_email}`}
          </Typography>
        </Container>
      </Box>
    </Box>
  )
}
