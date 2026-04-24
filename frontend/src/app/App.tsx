import { useEffect, useLayoutEffect, useState, type ReactElement } from 'react';
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from 'react-router';
import { apiFetch } from './api';
import { motion } from 'motion/react';
import { SignIn } from './components/SignIn';
import { SignUp } from './components/SignUp';
import { Home } from './components/Home';
import { UserHome } from './components/UserHome';
import { RestaurantProfile } from './components/RestaurantProfile';
import { UserProfile } from './components/UserProfile';
import { Messages } from './components/Messages';
import { Map } from './components/Map';
import { PhotoManagement } from './components/PhotoManagement';
import { AdminDashboard } from './components/AdminDashboard';
import { AdminRestaurantAccounts } from './components/AdminRestaurantAccounts';
import { AdminModeration } from './components/AdminModeration';
import { AdminPendingApprovals } from './components/AdminPendingApprovals';
import { AdminManageUsers } from './components/AdminManageUsers';
import { AdminLogs } from './components/AdminLogs';
import { PasswordResetForm } from './components/PasswordResetForm';
import { PasswordResetDone } from './components/PasswordResetDone';
import { PasswordResetConfirm } from './components/PasswordResetConfirm';
import { PasswordResetComplete } from './components/PasswordResetComplete';
import { ManageActivation } from './components/ManageActivation';
import { TwoFactorAuth } from './components/TwoFactorAuth';
import { ClaimRestaurant } from './components/ClaimRestaurant';
import { RestaurantDetail } from './components/RestaurantDetail';
import { AddReview } from './components/AddReview';
import { ReportContent } from './components/ReportContent';
import { SearchResults } from './components/SearchResults';
import { RestaurantComparison } from './components/RestaurantComparison';
import { Recommendations } from './components/Recommendations';
import { RestaurantForm } from './components/RestaurantForm';
import { FriendChat } from './components/FriendChat';
import { useAppContext, useLogout, type AccountType, type UserData } from './AppContext';

type LocationState = {
  adminPortal?: boolean;
  from?: string;
  resetUid?: string;
  resetToken?: string;
  pendingStart?: { id: number; name: string };
};

/** Sync legacy query params to path + router state (Django email links, ?admin). */
function UrlSync() {
  const navigate = useNavigate();
  const location = useLocation();

  useLayoutEffect(() => {
    const params = new URLSearchParams(location.search);
    const uidParam = params.get('resetUid');
    const tokenParam = params.get('resetToken');
    if (uidParam && tokenParam) {
      navigate('/password-reset/confirm/', {
        replace: true,
        state: { resetUid: uidParam, resetToken: tokenParam },
      });
      return;
    }
    if (params.has('admin')) {
      params.delete('admin');
      const qs = params.toString();
      const path = `${location.pathname}${qs ? `?${qs}` : ''}`;
      window.history.replaceState({}, '', path);
      navigate('/signin/', { replace: true, state: { adminPortal: true } });
    }
  }, [location.pathname, location.search, navigate]);

  return null;
}

function SessionBootstrap() {
  const { setUserData, setIsSessionLoading } = useAppContext();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await apiFetch('/api/auth/session/');
        const data = await r.json();
        if (cancelled) return;
        if (data.authenticated) {
          let accountType: UserData['accountType'] = 'diner';
          if (data.is_staff) accountType = 'admin';
          else if (data.role === 'restaurant') accountType = 'restaurant';
          setUserData({ username: data.username, accountType });
        }
      } catch {
        /* offline or CORS */
      } finally {
        if (!cancelled) {
          setIsSessionLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setUserData, setIsSessionLoading]);

  return null;
}

function RequireAuth({ children }: { children: ReactElement }) {
  const { userData, isSessionLoading } = useAppContext();
  const location = useLocation();
  
  // While session is loading, show nothing (prevents flashing signin during reload)
  if (isSessionLoading) {
    return null;
  }
  
  if (!userData) {
    return (
      <Navigate
        to="/signin/"
        replace
        state={{ from: `${location.pathname}${location.search}` }}
      />
    );
  }
  return children;
}

function RequireRole({
  allow,
  children,
}: {
  allow: AccountType[];
  children: ReactElement;
}) {
  const { userData, isSessionLoading } = useAppContext();
  
  // While session is loading, show nothing
  if (isSessionLoading) {
    return null;
  }
  
  if (!userData || !allow.includes(userData.accountType)) {
    return <Navigate to="/home/" replace />;
  }
  return children;
}

function OpeningScreen() {
  const navigate = useNavigate();
  const [showClickToStart, setShowClickToStart] = useState(false);

  const handleClick = () => {
    if (showClickToStart) {
      navigate('/home/');
    }
  };

  return (
    <div
      className="size-full flex items-center justify-center cursor-pointer"
      style={{ backgroundImage: 'radial-gradient(circle, #E06E7F, #FFF9F5)' }}
      onClick={handleClick}
    >
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          {['n', 'o', 'm', 'z'].map((letter, index) => (
            <motion.span
              key={index}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{
                opacity: 1,
                scale: [0.5, 1.2, 1],
              }}
              transition={{
                duration: 0.8,
                delay: index * 0.15,
                ease: 'easeOut',
              }}
              className="text-4xl text-white"
              style={{
                fontFamily: 'Montserrat, sans-serif',
                filter: 'drop-shadow(0 0 8px rgba(224, 110, 127, 0.6))',
              }}
            >
              {letter}
            </motion.span>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{
            duration: 0.5,
            delay: 1.1,
            ease: 'easeIn',
          }}
          onAnimationComplete={() => setShowClickToStart(true)}
          className="text-xs text-white"
          style={{
            fontFamily: 'Montserrat, sans-serif',
          }}
        >
          click to start
        </motion.p>
      </div>
    </div>
  );
}

function DashboardGate() {
  const { userData } = useAppContext();
  if (!userData) {
    return <Navigate to="/signin/" replace />;
  }
  if (userData.accountType === 'restaurant') {
    return <Navigate to="/restaurant-profile/" replace />;
  }
  if (userData.accountType === 'admin') {
    return <Navigate to="/nomz-admin/" replace />;
  }
  return <DinerDashboard />;
}

function DinerDashboard() {
  const navigate = useNavigate();
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <UserHome
        onLogout={logout}
        onViewProfile={() => navigate('/profile/')}
        onViewMessages={() => navigate('/messages/')}
        onViewFriendChat={() => navigate('/friends-chat/')}
        onNavigateMap={() => navigate('/map/')}
        onSearch={(q, neighborhood) => {
          const params = new URLSearchParams();
          if (q) params.set('q', q);
          if (neighborhood) params.set('neighborhood', neighborhood);
          navigate(`/search/?${params.toString()}`);
        }}
        onOpenRecommendations={() => navigate('/recommendations/')}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
        username={userData?.username || 'Diner'}
      />
    </div>
  );
}

function SignInPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUserData } = useAppContext();
  const state = location.state as LocationState | null;
  const adminPortal = Boolean(state?.adminPortal);
  const returnTo =
    state?.from && !state.from.startsWith('/signin') ? state.from : null;

  const afterAuth = (accountType: AccountType, username: string) => {
    setUserData({ username, accountType });
    if (returnTo) {
      navigate(returnTo);
      return;
    }
    if (accountType === 'diner') {
      navigate('/dashboard/');
    } else if (accountType === 'restaurant') {
      navigate('/restaurant-profile/');
    } else {
      navigate('/nomz-admin/');
    }
  };

  return (
    <div className="h-screen w-screen overflow-hidden">
      <SignIn
        onBackClick={() => navigate('/home/')}
        onSignIn={afterAuth}
        onForgotPassword={() => navigate('/password-reset/')}
        onTwoFactorRequired={() => navigate('/signin/2fa/', { state })}
        onSignUp={() => navigate('/register/')}
        adminPortal={adminPortal}
      />
    </div>
  );
}

function SignUpPage() {
  const navigate = useNavigate();
  const { setUserData } = useAppContext();

  return (
    <div className="h-screen w-screen overflow-hidden">
      <SignUp
        onBackClick={() => navigate('/home/')}
        onLoginClick={() => navigate('/signin/')}
        onSignUp={(accountType, username) => {
          setUserData({ username, accountType });
          if (accountType === 'diner') {
            navigate('/dashboard/');
          } else if (accountType === 'restaurant') {
            navigate('/restaurant-profile/');
          } else {
            navigate('/nomz-admin/');
          }
        }}
      />
    </div>
  );
}

function TwoFactorPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUserData } = useAppContext();
  const st = location.state as LocationState | null;
  const returnTo =
    st?.from && !st.from.startsWith('/signin') ? st.from : null;

  return (
    <div className="h-screen w-screen overflow-hidden">
      <TwoFactorAuth
        onBack={() => navigate('/signin/', { state: st })}
        onVerify={(data) => {
          let accountType: AccountType = 'diner';
          if (data.is_staff) accountType = 'admin';
          else if (data.role === 'restaurant') accountType = 'restaurant';
          setUserData({ username: data.username, accountType });
          if (returnTo) {
            navigate(returnTo);
            return;
          }
          if (accountType === 'restaurant') {
            navigate('/restaurant-profile/');
          } else if (accountType === 'admin') {
            navigate('/nomz-admin/');
          } else {
            navigate('/dashboard/');
          }
        }}
      />
    </div>
  );
}

function MapPage({ variant }: { variant: 'diner' | 'owner' | 'admin' }) {
  const navigate = useNavigate();
  const logout = useLogout((to) => navigate(to));

  const home =
    variant === 'admin'
      ? () => navigate('/nomz-admin/')
      : variant === 'owner'
        ? () => navigate('/restaurant-profile/')
        : () => navigate('/dashboard/');

  return (
    <div className="min-h-screen w-screen overflow-auto">
      <Map
        onNavigateHome={home}
        onNavigateMessages={() => navigate('/messages/')}
        onNavigateFriendChat={variant === 'diner' ? () => navigate('/friends-chat/') : undefined}
        onNavigateProfile={() =>
          variant === 'diner' ? navigate('/profile/') : navigate('/restaurant-profile/')
        }
        onLogout={logout}
        isAdmin={variant === 'admin'}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
      />
    </div>
  );
}

function MessagesPage({
  initialConversationId = null,
  pendingStartOverride = null,
}: {
  initialConversationId?: number | null;
  pendingStartOverride?: { id: number; name: string } | null;
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));
  const state = location.state as LocationState | null;
  const pending = pendingStartOverride ?? state?.pendingStart ?? null;

  const clearPendingState = () => {
    if (pendingStartOverride != null) {
      navigate('/messages/', { replace: true });
      return;
    }
    navigate(location.pathname, { replace: true, state: {} });
  };

  const mapTarget =
    userData?.accountType === 'restaurant'
      ? '/restaurant/map/'
      : userData?.accountType === 'admin'
        ? '/nomz-admin/map/'
        : '/map/';

  return (
    <div className="h-screen w-screen overflow-hidden">
      <Messages
        onNavigateMap={() => navigate(mapTarget)}
        onNavigateHome={() =>
          userData?.accountType === 'restaurant'
            ? navigate('/restaurant-profile/')
            : navigate('/dashboard/')
        }
        onNavigateProfile={() =>
          userData?.accountType === 'restaurant'
            ? navigate('/restaurant-profile/')
            : navigate('/profile/')
        }
        onNavigateFriendChat={userData?.accountType === 'diner' ? () => navigate('/friends-chat/') : undefined}
        onLogout={logout}
        accountType={userData?.accountType === 'restaurant' ? 'Restaurant' : 'Diner'}
        pendingStartRestaurantId={pending?.id ?? null}
        pendingStartRestaurantName={pending?.name ?? ''}
        onConsumedPendingStart={clearPendingState}
        initialConversationId={initialConversationId}
      />
    </div>
  );
}

function MessagesConversationRoute() {
  const { conversationId } = useParams();
  const id = conversationId ? parseInt(conversationId, 10) : NaN;
  if (!Number.isFinite(id)) {
    return <Navigate to="/messages/" replace />;
  }
  return <MessagesPage initialConversationId={id} />;
}

function MessagesRestaurantRoute() {
  const { restaurantId } = useParams();
  const id = restaurantId ? parseInt(restaurantId, 10) : NaN;
  const [pending, setPending] = useState<{ id: number; name: string } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!Number.isFinite(id)) return;
    let cancelled = false;
    void (async () => {
      try {
        const r = await apiFetch(`/api/restaurants/${id}/`);
        if (!r.ok) {
          if (!cancelled) setFailed(true);
          return;
        }
        const d = (await r.json()) as { name?: string };
        const name =
          typeof d.name === 'string' && d.name.trim() ? d.name.trim() : `Restaurant #${id}`;
        if (!cancelled) setPending({ id, name });
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!Number.isFinite(id)) {
    return <Navigate to="/messages/" replace />;
  }
  if (failed) {
    return <Navigate to="/messages/" replace />;
  }
  if (!pending) {
    return (
      <div
        className="h-screen w-screen flex items-center justify-center"
        style={{ backgroundColor: '#FFF9F5' }}
      >
        <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>Loading…</p>
      </div>
    );
  }
  return <MessagesPage pendingStartOverride={pending} />;
}

function RestaurantProfilePage() {
  const navigate = useNavigate();
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <RestaurantProfile
        onLogout={logout}
        username={userData?.username || 'Restaurant'}
        onNavigateMessages={() => navigate('/messages/')}
        onPhotoManagement={() => navigate('/restaurant/photos/')}
        onNavigateMap={() => navigate('/map/')}
        onNavigateRestaurantMap={() => navigate('/restaurant/map/')}
        onBack={() => navigate('/restaurant-profile/')}
        onManageActivation={() => navigate('/restaurant/activate/')}
        onClaimListing={() => navigate('/restaurant/claim/')}
        onRestaurantForm={() => navigate('/restaurant/edit/')}
      />
    </div>
  );
}

function UserProfilePage() {
  const navigate = useNavigate();
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <UserProfile
        onBack={() => navigate('/dashboard/')}
        onViewMessages={() => navigate('/messages/')}
        onViewFriendChat={() => navigate('/friends-chat/')}
        onNavigateMap={() => navigate('/map/')}
        onNavigateHome={() => navigate('/dashboard/')}
        onLogout={logout}
        username={userData?.username || 'Diner'}
      />
    </div>
  );
}

function RestaurantDetailPage() {
  const navigate = useNavigate();
  const { restaurantId } = useParams();
  const id = restaurantId ? parseInt(restaurantId, 10) : NaN;
  const { userData } = useAppContext();

  if (!Number.isFinite(id)) {
    return <Navigate to="/map/" replace />;
  }

  return (
    <div className="h-screen w-screen overflow-hidden">
      <RestaurantDetail
        restaurantId={id}
        onBack={() => {
          if (userData?.accountType === 'restaurant') navigate('/restaurant-profile/');
          else if (userData?.accountType === 'admin') navigate('/nomz-admin/');
          else navigate('/dashboard/');
        }}
        onWriteReview={(rid) => navigate(`/restaurant/${rid}/review/`)}
        onReportReview={(reviewId) =>
          navigate(`/report/review/${reviewId}/`, { state: { fromDetail: id } })
        }
        onReportOwner={(userId) =>
          navigate(`/report/user/${userId}/`, { state: { fromDetail: id } })
        }
        onStartConversation={
          userData?.accountType === 'diner'
            ? (rid) => navigate(`/messages/restaurant/${rid}/`)
            : undefined
        }
      />
    </div>
  );
}

function AddReviewPage() {
  const navigate = useNavigate();
  const { restaurantId } = useParams();
  const id = restaurantId ? parseInt(restaurantId, 10) : NaN;

  if (!Number.isFinite(id)) {
    return <Navigate to="/map/" replace />;
  }

  return (
    <div className="h-screen w-screen overflow-hidden">
      <AddReview
        restaurantId={id}
        restaurantName=""
        onBack={() => navigate(`/restaurant/${id}/`)}
        onSuccess={() => navigate(`/restaurant/${id}/`)}
      />
    </div>
  );
}

function ReportPage() {
  const navigate = useNavigate();
  const { contentType, contentId } = useParams();
  const id = contentId ? parseInt(contentId, 10) : NaN;
  const location = useLocation();
  const fromDetail = (location.state as { fromDetail?: number } | null)?.fromDetail;

  if (!Number.isFinite(id) || (contentType !== 'review' && contentType !== 'user')) {
    return <Navigate to="/map/" replace />;
  }

  const back = () =>
    fromDetail != null
      ? navigate(`/restaurant/${fromDetail}/`)
      : navigate(-1);

  return (
    <div className="h-screen w-screen overflow-hidden">
      <ReportContent
        contentType={contentType}
        contentId={id}
        onBack={back}
        onSuccess={back}
      />
    </div>
  );
}

function SearchPage() {
  const navigate = useNavigate();
  const [sp] = useSearchParams();
  const q = sp.get('q') ?? '';
  const initialNeighborhood = sp.get('neighborhood') ?? '';
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <SearchResults
        initialQuery={q}
        initialNeighborhood={initialNeighborhood}
        onBack={() => navigate('/dashboard/')}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
        onNavigateMap={() => navigate('/map/')}
        onNavigateMessages={() => navigate('/messages/')}
        onNavigateProfile={() => navigate('/profile/')}
        onNavigateCompare={() => navigate('/compare/')}
        onLogout={logout}
        username={userData?.username || 'Diner'}
      />
    </div>
  );
}

function ComparisonPage() {
  const navigate = useNavigate();

  return (
    <div className="h-screen w-screen overflow-hidden">
      <RestaurantComparison
        onBack={() => navigate('/search/')}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
      />
    </div>
  );
}

function RecommendationsPage() {
  const navigate = useNavigate();
  const { userData } = useAppContext();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <Recommendations
        onBack={() => navigate('/dashboard/')}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
        onNavigateMap={() => navigate('/map/')}
        onNavigateMessages={() => navigate('/messages/')}
        onNavigateProfile={() => navigate('/profile/')}
        onOpenPreferences={() => navigate('/profile/')}
        onNavigateFriendChat={() => navigate('/friends-chat/')}
        onLogout={logout}
        username={userData?.username || 'Diner'}
      />
    </div>
  );
}

function FriendChatPage() {
  const navigate = useNavigate();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <FriendChat
        onNavigateHome={() => navigate('/dashboard/')}
        onNavigateMap={() => navigate('/map/')}
        onNavigateProfile={() => navigate('/profile/')}
        onNavigateMessages={() => navigate('/messages/')}
        onSelectRestaurant={(id) => navigate(`/restaurant/${id}/`)}
        onLogout={logout}
      />
    </div>
  );
}

function PasswordResetConfirmPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const state = location.state as LocationState | null;

  return (
    <div className="h-screen w-screen overflow-hidden">
      <PasswordResetConfirm
        onBack={() => navigate('/signin/')}
        onSubmit={() => navigate('/password-reset/complete/')}
        isValidLink={Boolean(state?.resetUid && state?.resetToken)}
        uid={state?.resetUid}
        token={state?.resetToken}
      />
    </div>
  );
}

function AdminHomePage() {
  const navigate = useNavigate();
  const logout = useLogout((to) => navigate(to));

  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminDashboard
        onLogout={logout}
        onNavigateMap={() => navigate('/nomz-admin/map/')}
        onViewModeration={() => navigate('/nomz-admin/moderation/')}
        onViewPendingApprovals={() => navigate('/nomz-admin/pending-approvals/')}
        onViewPendingUsers={() => navigate('/nomz-admin/users/')}
        onViewLogs={() => navigate('/nomz-admin/logs/')}
        onViewApprovedAccounts={() => navigate('/nomz-admin/approved-accounts/')}
        onViewRejectedAccounts={() => navigate('/nomz-admin/rejected-accounts/')}
      />
    </div>
  );
}

function LogoutRoute() {
  const navigate = useNavigate();
  const { setUserData } = useAppContext();

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        await apiFetch('/api/auth/logout/', { method: 'POST' });
      } catch {
        /* ignore */
      }
      if (!cancelled) {
        setUserData(null);
        navigate('/home/', { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate, setUserData]);

  return (
    <div
      className="h-screen w-screen flex items-center justify-center"
      style={{ backgroundColor: '#FFF9F5' }}
    >
      <p style={{ fontFamily: 'Montserrat, sans-serif', color: '#666' }}>Signing out…</p>
    </div>
  );
}

/** Legacy Django password-reset links: `/reset/<uidb64>/<token>/`. */
function PasswordResetFromDjangoLink() {
  const { uidb64, token } = useParams<{ uidb64: string; token: string }>();
  const navigate = useNavigate();
  if (!uidb64 || !token) {
    return <Navigate to="/password-reset/" replace />;
  }
  return (
    <div className="h-screen w-screen overflow-hidden">
      <PasswordResetConfirm
        onBack={() => navigate('/password-reset/')}
        onSubmit={() => navigate('/password-reset/complete/')}
        isValidLink
        uid={uidb64}
        token={token}
      />
    </div>
  );
}

function AdminModerationResolvePage() {
  const { reportId } = useParams();
  const id = reportId ? parseInt(reportId, 10) : NaN;
  const navigate = useNavigate();
  if (!Number.isFinite(id)) {
    return <Navigate to="/nomz-admin/moderation/" replace />;
  }
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminModeration onBack={() => navigate('/nomz-admin/')} initialReportId={id} />
    </div>
  );
}

function TrailingSlashRedirect({ to }: { to: string }) {
  return <Navigate to={to} replace />;
}

export default function App() {
  return (
    <>
      <UrlSync />
      <SessionBootstrap />
      <Routes>
        <Route path="/" element={<OpeningScreen />} />
        <Route path="/home/" element={<HomeScreen />} />
        <Route path="/signin/" element={<SignInPage />} />
        {/* Same as Django two_factor:login path; dev (Vite) may load SPA here without server redirect */}
        <Route path="/account/login/" element={<Navigate to="/signin/" replace />} />
        <Route path="/signin/2fa/" element={<TwoFactorPage />} />
        <Route path="/register/" element={<SignUpPage />} />
        <Route path="/logout/" element={<LogoutRoute />} />

        <Route path="/password-reset/" element={<PasswordResetShell />} />
        <Route path="/password-reset/done/" element={<PasswordResetDoneShell />} />
        <Route path="/password-reset/confirm/" element={<PasswordResetConfirmPage />} />
        <Route path="/password-reset/complete/" element={<PasswordResetCompleteShell />} />
        <Route path="/reset/done/" element={<PasswordResetCompleteShell />} />
        <Route path="/reset/:uidb64/:token/" element={<PasswordResetFromDjangoLink />} />

        <Route
          path="/restaurant/availability/"
          element={<Navigate to="/restaurant-profile/" replace />}
        />
        <Route
          path="/restaurant/communication/"
          element={<Navigate to="/restaurant-profile/" replace />}
        />
        <Route
          path="/restaurant/photos/upload/"
          element={<Navigate to="/restaurant/photos/" replace />}
        />

        <Route
          path="/dashboard/"
          element={
            <RequireAuth>
              <DashboardGate />
            </RequireAuth>
          }
        />

        <Route
          path="/map/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <MapPage variant="diner" />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/map/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <MapPage variant="owner" />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/map/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <MapPage variant="admin" />
              </RequireRole>
            </RequireAuth>
          }
        />

        <Route
          path="/messages/conversations/:conversationId/"
          element={
            <RequireAuth>
              <MessagesConversationRoute />
            </RequireAuth>
          }
        />
        <Route
          path="/messages/restaurant/:restaurantId/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <MessagesRestaurantRoute />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/messages/"
          element={
            <RequireAuth>
              <MessagesPage />
            </RequireAuth>
          }
        />

        <Route
          path="/profile/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <UserProfilePage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/preferences/"
          element={<TrailingSlashRedirect to="/profile/" />}
        />

        <Route
          path="/recommendations/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <RecommendationsPage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/friends-chat/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <FriendChatPage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/search/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <SearchPage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/compare/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <ComparisonPage />
              </RequireRole>
            </RequireAuth>
          }
        />

        <Route
          path="/restaurant-profile/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <RestaurantProfilePage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/photos/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <PhotoManagementShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/claim/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <ClaimShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/create/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <RestaurantFormShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/edit/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <RestaurantFormShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/restaurant/activate/"
          element={
            <RequireAuth>
              <RequireRole allow={['restaurant']}>
                <ManageActivationShell />
              </RequireRole>
            </RequireAuth>
          }
        />

        <Route path="/restaurant/:restaurantId/" element={<RestaurantDetailPage />} />
        <Route
          path="/restaurant/:restaurantId/review/"
          element={
            <RequireAuth>
              <RequireRole allow={['diner']}>
                <AddReviewPage />
              </RequireRole>
            </RequireAuth>
          }
        />

        <Route
          path="/report/:contentType/:contentId/"
          element={
            <RequireAuth>
              <ReportPage />
            </RequireAuth>
          }
        />

        <Route
          path="/nomz-admin/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminHomePage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/moderation/resolve/:reportId/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminModerationResolvePage />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/moderation/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminModerationShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/approve/:userId/"
          element={<Navigate to="/nomz-admin/pending-approvals/" replace />}
        />
        <Route
          path="/nomz-admin/reject/:userId/"
          element={<Navigate to="/nomz-admin/pending-approvals/" replace />}
        />
        <Route
          path="/nomz-admin/users/:userId/toggle/"
          element={<Navigate to="/nomz-admin/users/" replace />}
        />
        <Route
          path="/nomz-admin/pending-approvals/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminPendingShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/users/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminUsersShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/logs/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminLogsShell />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/approved-accounts/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminAccountsShell kind="approved" />
              </RequireRole>
            </RequireAuth>
          }
        />
        <Route
          path="/nomz-admin/rejected-accounts/"
          element={
            <RequireAuth>
              <RequireRole allow={['admin']}>
                <AdminAccountsShell kind="rejected" />
              </RequireRole>
            </RequireAuth>
          }
        />

        <Route path="/admin-login/" element={<Navigate to="/signin/" replace state={{ adminPortal: true }} />} />

        {/* No trailing slash */}
        <Route path="/home" element={<Navigate to="/home/" replace />} />
        <Route path="*" element={<Navigate to="/home/" replace />} />
      </Routes>
    </>
  );
}

function HomeScreen() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <Home onSignInClick={() => navigate('/signin/')} onSignUpClick={() => navigate('/register/')} />
    </div>
  );
}

function PasswordResetShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <PasswordResetForm
        onBack={() => navigate('/home/')}
        onSubmit={() => navigate('/password-reset/done/')}
      />
    </div>
  );
}

function PasswordResetDoneShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <PasswordResetDone onBack={() => navigate('/signin/')} />
    </div>
  );
}

function PasswordResetCompleteShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <PasswordResetComplete onLoginClick={() => navigate('/signin/')} />
    </div>
  );
}

function PhotoManagementShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <PhotoManagement onBack={() => navigate('/restaurant-profile/')} />
    </div>
  );
}

function ClaimShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <ClaimRestaurant onBack={() => navigate('/restaurant-profile/')} />
    </div>
  );
}

function RestaurantFormShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <RestaurantForm onBack={() => navigate('/restaurant-profile/')} />
    </div>
  );
}

function ManageActivationShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <ManageActivation
        onBack={() => navigate('/restaurant-profile/')}
        onToggle={() => navigate('/restaurant-profile/')}
      />
    </div>
  );
}

function AdminModerationShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminModeration onBack={() => navigate('/nomz-admin/')} />
    </div>
  );
}

function AdminPendingShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminPendingApprovals onBack={() => navigate('/nomz-admin/')} />
    </div>
  );
}

function AdminUsersShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminManageUsers onBack={() => navigate('/nomz-admin/')} />
    </div>
  );
}

function AdminLogsShell() {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminLogs onBack={() => navigate('/nomz-admin/')} />
    </div>
  );
}

function AdminAccountsShell({ kind }: { kind: 'approved' | 'rejected' }) {
  const navigate = useNavigate();
  return (
    <div className="h-screen w-screen overflow-hidden">
      <AdminRestaurantAccounts listKind={kind} onBack={() => navigate('/nomz-admin/')} />
    </div>
  );
}
