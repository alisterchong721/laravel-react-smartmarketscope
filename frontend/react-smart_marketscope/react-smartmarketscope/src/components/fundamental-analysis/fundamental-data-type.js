import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Grid,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import RefreshIcon from '@mui/icons-material/Refresh';
import Sidebar from '../sidebar';
import './fundamental-analysis.css';

const { Title, Text } = Typography;
const API_URL = 'http://127.0.0.1:8000/api';

const currencyOptions = [
  { label: 'All currencies', value: 'ALL' },
  { label: 'USD', value: 'USD' },
  { label: 'EUR', value: 'EUR' },
  { label: 'GBP', value: 'GBP' },
  { label: 'JPY', value: 'JPY' },
  { label: 'AUD', value: 'AUD' },
  { label: 'CAD', value: 'CAD' },
];

const impactColor = {
  Bullish: 'green',
  Bearish: 'red',
  Neutral: 'default',
};

const formatApiDate = (date) => date.toISOString().slice(0, 10);

const getWeekRange = (weekOffset = 0) => {
  const start = new Date();
  const mondayOffset = (start.getDay() + 6) % 7;

  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - mondayOffset + weekOffset * 7);

  const end = new Date(start);
  end.setDate(start.getDate() + 6);

  return {
    start,
    end,
    startDate: formatApiDate(start),
    endDate: formatApiDate(end),
  };
};

const formatWeekLabel = ({ start, end }) =>
  `${start.toLocaleDateString(undefined, {
    month: 'short',
    day: '2-digit',
  })} - ${end.toLocaleDateString(undefined, {
    month: 'short',
    day: '2-digit',
    year: 'numeric',
  })}`;

const formatDateTime = (date, time) => {
  if (!date) return 'N/A';

  const parsed = new Date(`${date}T${time || '00:00:00'}`);

  if (Number.isNaN(parsed.getTime())) {
    return `${date} ${time || ''}`.trim();
  }

  return parsed.toLocaleString(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const FundamentalDataType = () => {
  const { useBreakpoint } = Grid;
  const screens = useBreakpoint();

  const [calendar, setCalendar] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [currency, setCurrency] = useState('ALL');
  const [weekOffset, setWeekOffset] = useState(0);

  const weekRange = useMemo(() => getWeekRange(weekOffset), [weekOffset]);

  const fetchCalendar = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_URL}/fundamental/calendar`, {
        params: {
          currency: currency === 'ALL' ? undefined : currency,
          importance: 'High',
          start_date: weekRange.startDate,
          end_date: weekRange.endDate,
          limit: 250,
        },
      });

      setCalendar(response.data?.data || []);
      setLastUpdated(new Date().toISOString());
    } catch (requestError) {
      setError(
        requestError.response?.data?.message ||
          requestError.response?.data?.error ||
          requestError.message ||
          'Unable to load economic calendar'
      );
    } finally {
      setLoading(false);
    }
  }, [currency, weekRange.endDate, weekRange.startDate]);

  useEffect(() => {
    fetchCalendar();
  }, [fetchCalendar]);

  const summary = useMemo(() => {
    const pending = calendar.filter((event) => !event.actual).length;
    const bullish = calendar.filter((event) => event.impact === 'Bullish').length;
    const bearish = calendar.filter((event) => event.impact === 'Bearish').length;

    return { pending, bullish, bearish };
  }, [calendar]);

  const columns = [
    {
      title: 'Economic Data',
      dataIndex: 'event',
      key: 'event',
      ellipsis: true,
      render: (value, record) => (
        <Space size={8} wrap>
          <Tag color="blue">{record.currency}</Tag>
          <span>{value}</span>
        </Space>
      ),
      filters: currencyOptions
        .filter((item) => item.value !== 'ALL')
        .map((item) => ({ text: item.label, value: item.value })),
      onFilter: (value, record) => record.currency === value,
    },
    {
      title: 'Actual',
      dataIndex: 'actual',
      key: 'actual',
      width: 150,
      render: (value, record) => {
        const displayValue =
          value || (record.actual_status === 'not_applicable' ? 'N/A' : 'Pending');
        const className = value
          ? `fundamental-calendar-actual fundamental-calendar-actual-${record.actual_color || 'default'}`
          : 'fundamental-calendar-actual fundamental-calendar-actual-default';

        return <Text className={className}>{displayValue}</Text>;
      },
    },
    {
      title: 'Forecast',
      dataIndex: 'forecast',
      key: 'forecast',
      width: 110,
      render: (value) => value || 'N/A',
    },
    {
      title: 'Previous',
      dataIndex: 'previous',
      key: 'previous',
      width: 110,
      render: (value) => value || 'N/A',
    },
    {
      title: 'Date',
      dataIndex: 'date',
      key: 'date',
      width: 150,
      render: (_, record) => formatDateTime(record.date, record.time),
      sorter: (a, b) =>
        `${a.date || ''}${a.time || ''}`.localeCompare(
          `${b.date || ''}${b.time || ''}`
        ),
    },
    {
      title: 'Impact',
      dataIndex: 'impact',
      key: 'impact',
      width: 120,
      render: (value) => <Tag color={impactColor[value] || 'default'}>{value}</Tag>,
    },
    {
      title: 'Source',
      dataIndex: 'source',
      key: 'source',
      width: 190,
      render: (value, record) => (
        <Space size={4} wrap>
          <Tag color="blue">{value || 'Forex Factory'}</Tag>
          {record.actual_source && <Tag color="cyan">Actual: {record.actual_source}</Tag>}
        </Space>
      ),
    },
  ];

  return (
    <Sidebar>
      <div className="fundamental-calendar-page">
        <Row justify="space-between" gutter={[16, 16]} align="middle">
          <Col xs={24} lg={12}>
            <Title level={2} className="fundamental-calendar-title">
              Economic Calendar
            </Title>
            {lastUpdated && (
              <Text type="secondary">
                Last refreshed {new Date(lastUpdated).toLocaleTimeString()}.
              </Text>
            )}
          </Col>

          <Col xs={24} lg={12}>
            <Space
              wrap
              className="fundamental-calendar-actions"
              style={{ justifyContent: screens.xs ? 'stretch' : 'flex-end' }}
            >
              <Select
                value={currency}
                onChange={setCurrency}
                options={currencyOptions}
                className="fundamental-calendar-select"
              />
              <Button
                icon={<LeftOutlined />}
                onClick={() => setWeekOffset((current) => current - 1)}
              />
              <Text className="fundamental-calendar-week-label">
                {formatWeekLabel(weekRange)}
              </Text>
              <Button
                icon={<RightOutlined />}
                onClick={() => setWeekOffset((current) => current + 1)}
              />
              <Button icon={<RefreshIcon />} onClick={fetchCalendar} loading={loading}>
                Refresh
              </Button>
            </Space>
          </Col>
        </Row>

        {error && (
          <Alert
            type="error"
            showIcon
            message="Calendar unavailable"
            description={error}
            className="fundamental-calendar-alert"
          />
        )}

        <Row gutter={[16, 16]} className="fundamental-calendar-summary">
          <Col xs={24} sm={8}>
            <Card>
              <Statistic title="Loaded Events" value={calendar.length} />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic title="Pending Releases" value={summary.pending} />
            </Card>
          </Col>
          <Col xs={24} sm={8}>
            <Card>
              <Statistic
                title="Bullish / Bearish"
                value={`${summary.bullish} / ${summary.bearish}`}
              />
            </Card>
          </Col>
        </Row>

        <Card className="fundamental-calendar-table-card">
          <Table
            columns={columns}
            dataSource={calendar}
            loading={loading}
            rowKey={(record) => record.id || `${record.date}-${record.time}-${record.event}`}
            scroll={{ x: 1100 }}
            pagination={{ pageSize: 12, showSizeChanger: false }}
            locale={{
              emptyText: (
                <Empty description="No calendar events found for the selected filters" />
              ),
            }}
          />
        </Card>
      </div>
    </Sidebar>
  );
};

export default FundamentalDataType;
