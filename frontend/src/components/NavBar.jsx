import {
  AppBar, Box, Button, Toolbar, Typography,
} from '@mui/material'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useBranding } from '../branding'

export default function NavBar() {
  const branding = useBranding()
  const { user, logout, canAuthor } = useAuth()
  const navigate = useNavigate()

  return (
    <AppBar position="sticky" color="primary" elevation={1}>
      <Toolbar>
        <Box component={Link} to="/" sx={{
          display: 'flex', alignItems: 'center', gap: 1.5,
          textDecoration: 'none', color: 'inherit', flexGrow: 1,
        }}>
          {branding.logo_url && (
            <img src={branding.logo_url} alt="" style={{ height: 34 }} />
          )}
          <Typography variant="h6" fontWeight={700}>
            {branding.product_name}
          </Typography>
        </Box>
        <Button color="inherit" component={Link} to="/">Catalog</Button>
        {user && <Button color="inherit" component={Link} to="/my">My learning</Button>}
        {canAuthor && <Button color="inherit" component={Link} to="/admin">Studio</Button>}
        <Button color="inherit" component={Link} to="/verify">Verify</Button>
        {user ? (
          <Button color="inherit" onClick={() => { logout(); navigate('/') }}>
            Log out
          </Button>
        ) : (
          <Button color="inherit" variant="outlined" component={Link} to="/login" sx={{ ml: 1 }}>
            Sign in
          </Button>
        )}
      </Toolbar>
    </AppBar>
  )
}
