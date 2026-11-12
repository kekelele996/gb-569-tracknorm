import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import Alerts from '../pages/Alerts';
import Carriers from '../pages/Carriers';
import Login from '../pages/Login';
import Mappings from '../pages/Mappings';
import WaybillDetail from '../pages/WaybillDetail';
import Waybills from '../pages/Waybills';
import { RequireAuth, RequirePermission } from './guards';

function Protected({ permission, children }: { permission: string; children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>
        <RequirePermission permission={permission}>{children}</RequirePermission>
      </AppShell>
    </RequireAuth>
  );
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/waybills" replace />} />
      <Route path="/waybills" element={<Protected permission="waybill:read"><Waybills /></Protected>} />
      <Route path="/waybills/:waybillId" element={<Protected permission="waybill:read"><WaybillDetail /></Protected>} />
      <Route path="/mappings" element={<Protected permission="mapping:read"><Mappings /></Protected>} />
      <Route path="/alerts" element={<Protected permission="alert:read"><Alerts /></Protected>} />
      <Route path="/carriers" element={<Protected permission="carrier:read"><Carriers /></Protected>} />
      <Route path="*" element={<Navigate to="/waybills" replace />} />
    </Routes>
  );
}
