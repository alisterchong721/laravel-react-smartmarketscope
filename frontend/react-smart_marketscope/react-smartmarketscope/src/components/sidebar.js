import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { logoutRequest } from '../actions/authActions';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  UserOutlined,
  LoginOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import LogoutIcon from '@mui/icons-material/Logout';
import LanguageIcon from '@mui/icons-material/Language';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import HomeIcon from '@mui/icons-material/Home';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import MonetizationOnIcon from '@mui/icons-material/MonetizationOn';
import StackedBarChartIcon from '@mui/icons-material/StackedBarChart';
import SummarizeIcon from '@mui/icons-material/Summarize';
import QueryStatsIcon from '@mui/icons-material/QueryStats';

import {
  Alert,
  Breadcrumb,
  Layout,
  Menu,
  theme,
  Typography,
  Image,
  message,
  Modal,
  Avatar,
} from 'antd';
import '../styles/global.css';
import SiteLogo from '../assets/site-logo.png';

const { Content, Sider } = Layout;
const { Link: AntLink } = Typography;

const siderStyle = {
  overflow: 'auto',
  height: '100vh',
  position: 'sticky',
  insetInlineStart: 0,
  top: 0,
  bottom: 0,
  left: 0,
  padding: 0,
  scrollbarWidth: 'thin',
  scrollbarGutter: 'stable',
};

const titleCasePathPart = (value) =>
  (value || '')
    .split('-')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');

const formatPairLabel = (value) => {
  const normalized = (value || '').toUpperCase();

  return normalized.length === 6
    ? `${normalized.slice(0, 3)}/${normalized.slice(3)}`
    : normalized;
};

const buildBreadcrumbItems = (pathname) => {
  const parts = pathname.split('/').filter(Boolean);

  if (!parts.length || parts[0] === 'home') {
    return [{ title: 'Home' }];
  }

  if (parts[0] === 'overview') {
    return [{ title: 'Overview Setup' }];
  }

  if (parts[0] === 'fundamental') {
    if (parts[1] === 'pair') {
      return [
        { title: 'Fundamental Analysis' },
        { title: 'Currency Pairs' },
        { title: formatPairLabel(parts[2] || 'EURUSD') },
      ];
    }

    if (parts[1] === 'country') {
      return [
        { title: 'Fundamental Analysis' },
        { title: 'Countries' },
        { title: titleCasePathPart(parts[2] || 'US') },
      ];
    }

    if (parts[1] === 'data-type') {
      return [
        { title: 'Fundamental Analysis' },
        { title: 'Economic Calendar' },
      ];
    }
  }

  if (parts[0] === 'sentimental') {
    if (parts[1] === 'cot-positions') {
      return [
        { title: 'Sentimental Analysis' },
        { title: 'COT Positions' },
        ...(parts[3] ? [{ title: formatPairLabel(parts[3]) }] : []),
      ];
    }

    if (parts[1] === 'retail-sentiment') {
      return [
        { title: 'Sentimental Analysis' },
        { title: 'Retail Sentiment' },
        ...(parts[3] ? [{ title: formatPairLabel(parts[3]) }] : []),
      ];
    }

    if (parts[1] === 'news-sentiment') {
      return [
        { title: 'Sentimental Analysis' },
        { title: 'News Sentiment' },
      ];
    }
  }

  if (parts[0] === 'seasonality') {
    return [
      { title: 'Seasonality Analysis' },
      { title: formatPairLabel(parts[1] || 'EURUSD') },
    ];
  }

  if (parts[0] === 'trading-journal') {
    return [{ title: 'Trading Journal' }];
  }

  return parts.map((part) => ({ title: titleCasePathPart(part) }));
};

const Sidebar = (props) => {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedKeys, setSelectedKeys] = useState(['/home']);
  const [openKeys, setOpenKeys] = useState(['sub1']);
  const location = useLocation();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const [messageApi, contextHolder] = message.useMessage();

  const { user, isAuthenticated } = useSelector((state) => state.auth);

  const handleLogout = () => {
    Modal.confirm({
      title: 'Are you sure you want to logout?',
      icon: <LogoutIcon style={{ color: '#ff4d4f' }} />,
      content: 'You will need to login again to access your journal.',
      okText: 'Logout',
      okType: 'danger',
      cancelText: 'Cancel',
      centered: true,
      onOk() {
        dispatch(logoutRequest());
        messageApi.success('Logged out successfully');
        navigate('/login');
      },
    });
  };

  const getItem = (label, key, icon, children) => ({
    key,
    icon,
    children,
    label,
  });

  const menuItems = [
    getItem('Home', '/home', <HomeIcon />),
    getItem('Overview Setup', '/overview', <SummarizeIcon />),
    getItem('Fundamental Analysis', 'sub1', <AccountBalanceIcon />, [
      getItem('Currency Pairs', 'sub-sub1', <MonetizationOnIcon />, [
        getItem('EURUSD', '/fundamental/pair/eurusd'),
        getItem('GBPUSD', '/fundamental/pair/gbpusd'),
        getItem('AUDUSD', '/fundamental/pair/audusd'),
        getItem('USDCAD', '/fundamental/pair/usdcad'),
        getItem('USDJPY', '/fundamental/pair/usdjpy'),
      ]),
      getItem('Economic Calendar', '/fundamental/data-type', <StackedBarChartIcon />),
      getItem('Countries', 'sub-sub2', <LanguageIcon />, [
        getItem('United States', '/fundamental/country/us'),
        getItem('United Kingdom', '/fundamental/country/uk'),
        getItem('Europe', '/fundamental/country/eurozone'),
        getItem('Australia', '/fundamental/country/australia'),
        getItem('Canada', '/fundamental/country/canada'),
        getItem('Japan', '/fundamental/country/japan'),
      ]),
    ]),
    getItem('Sentimental Analysis', 'sub2', <UserOutlined />, [
      getItem('COT Positions', '/sentimental/cot-positions'),
      getItem('Retail Sentiment', '/sentimental/retail-sentiment'),
      getItem('News Sentiment', '/sentimental/news-sentiment'),
    ]),
    getItem('Seasonality Analysis', 'sub4', <QueryStatsIcon />, [
      getItem('EURUSD', '/seasonality/eurusd'),
      getItem('GBPUSD', '/seasonality/gbpusd'),
      getItem('AUDUSD', '/seasonality/audusd'),
      getItem('USDCAD', '/seasonality/usdcad'),
      getItem('USDJPY', '/seasonality/usdjpy'),
    ]),
    getItem('Trading Journal', '/trading-journal', <MenuBookIcon />),
    { type: 'divider' },
  ];

  if (isAuthenticated) {
    menuItems.push(getItem('Logout', 'logout', <LogoutIcon />));
  } else {
    menuItems.push(getItem('Login', '/login', <LoginOutlined />));
    menuItems.push(getItem('Register', '/register', <UserAddOutlined />));
  }

  const handleMenuClick = (e) => {
    if (e.key === 'logout') {
      handleLogout();
    } else if (e.key.startsWith('/')) {
      navigate(e.key);
    }
  };

  useEffect(() => {
    if (location.pathname.startsWith('/sentimental/cot-positions')) {
      setSelectedKeys(['/sentimental/cot-positions']);
      return;
    }

    if (location.pathname.startsWith('/sentimental/retail-sentiment')) {
      setSelectedKeys(['/sentimental/retail-sentiment']);
      return;
    }

    if (location.pathname.startsWith('/sentimental/news-sentiment')) {
      setSelectedKeys(['/sentimental/news-sentiment']);
      return;
    }

    if (location.pathname === '/seasonality') {
      setSelectedKeys(['/seasonality/eurusd']);
      return;
    }

    setSelectedKeys([location.pathname]);
  }, [location.pathname]);

  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  return (
    <>
      {contextHolder}
      <Layout style={{ minHeight: '100vh', display: 'flex' }}>
        <Sider
          style={siderStyle}
          collapsible
          collapsed={collapsed}
          onCollapse={(value) => setCollapsed(value)}
        >
          {/* ORIGINAL LOGO CONTAINER LOGIC */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              padding: '16px 0',
            }}
          >
            <div
              style={{
                backgroundColor: '#FFFFFF',
                borderRadius: '50%',
                padding: collapsed ? '6px 12px' : '5px 20px',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}
            >
              <AntLink
                onClick={() => navigate('/home')}
                style={{ cursor: 'pointer' }}
              >
                <Image
                  width={collapsed ? 40 : 80}
                  alt="Smart MarketScope"
                  src={SiteLogo}
                  preview={false}
                />
              </AntLink>
            </div>
          </div>

          {/* UPDATED USER INFO: NO "ACCOUNT" WORD */}
          {isAuthenticated && user && !collapsed && (
            <div style={{ padding: '10px 16px', textAlign: 'center' }}>
              <Avatar
                size={40}
                icon={<UserOutlined />}
                style={{ backgroundColor: '#1890ff', marginBottom: '8px' }}
              />
              <div
                style={{
                  color: '#fff',
                  fontSize: '12px',
                  wordBreak: 'break-all',
                }}
              >
                {user.email}
              </div>
            </div>
          )}

          <Menu
            theme="dark"
            selectedKeys={selectedKeys}
            openKeys={openKeys}
            onOpenChange={setOpenKeys}
            mode="inline"
            items={menuItems}
            onClick={handleMenuClick}
          />
        </Sider>

        <Layout>
          <Content style={{ margin: '0 16px' }}>
            <Breadcrumb
              style={{ margin: '16px 0' }}
              items={buildBreadcrumbItems(location.pathname)}
            />
            <Alert
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
              message="Trading and investing involve high risk and may result in losses. Smart MarketScope is for analysis only and is not financial advice."
            />
            <div
              style={{
                padding: 24,
                minHeight: 360,
                background: colorBgContainer,
                borderRadius: borderRadiusLG,
                width: '100%',
                marginBottom: '20px',
              }}
            >
              {props.children}
            </div>
          </Content>
        </Layout>
      </Layout>
    </>
  );
};

export default Sidebar;
