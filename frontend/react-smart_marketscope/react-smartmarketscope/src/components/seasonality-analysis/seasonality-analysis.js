import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Column, Line } from '@ant-design/charts';
import { useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Col,
  Empty,
  Row,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import Sidebar from '../sidebar';
import './seasonality-analysis.css';

const { Title, Text } = Typography;

const API_URL = process.env.REACT_APP_API_URL || '/api';

const DEFAULT_ASSETS = ['EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDJPY'];
const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];

const formatSignedPercent = (value) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '-';
  }

  const numeric = Number(value);
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`;
};

const valueClassName = (value) =>
  Number(value || 0) >= 0 ? 'seasonality-positive' : 'seasonality-negative';

const SeasonalityAnalysis = () => {
  const { asset: routeAsset } = useParams();
  const [years, setYears] = useState(10);
  const [selectedMonth, setSelectedMonth] = useState(new Date().getMonth() + 1);
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const selectedAsset = DEFAULT_ASSETS.includes(routeAsset?.toUpperCase())
    ? routeAsset.toUpperCase()
    : DEFAULT_ASSETS[0];

  const fetchSeasonality = async (refresh = false) => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(`${API_URL}/seasonality`, {
        params: {
          assets: selectedAsset,
          period: 'monthly',
          years,
          refresh: refresh ? 1 : undefined,
        },
      });

      setPayload(response.data?.data || response.data);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message ||
          requestError.message ||
          'Failed to fetch seasonality data'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSeasonality(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAsset, years]);

  const selectedItem = useMemo(() => payload?.items?.[0] || null, [payload]);

  const monthlyChartData = useMemo(() => {
    return (selectedItem?.monthly || []).map((month) => ({
      month: month.month_short,
      month_number: month.month,
      average_return: month.average_return,
    }));
  }, [selectedItem]);

  const yearlyChartData = useMemo(() => {
    return (selectedItem?.yearly || []).map((year) => ({
      year: String(year.year),
      return_percent: year.return_percent,
    }));
  }, [selectedItem]);

  const selectedMonthData = useMemo(
    () => (selectedItem?.monthly || []).find((month) => month.month === selectedMonth) || null,
    [selectedItem, selectedMonth]
  );

  const monthHistoryRows = useMemo(
    () =>
      (selectedMonthData?.history || []).map((row) => ({
        key: row.year,
        ...row,
      })),
    [selectedMonthData]
  );

  const selectedMonthChartData = useMemo(
    () =>
      monthHistoryRows.map((row) => ({
        year: String(row.year),
        return_percent: row.return_percent,
      })),
    [monthHistoryRows]
  );

  const monthlyConfig = {
    data: monthlyChartData,
    xField: 'month',
    yField: 'average_return',
    height: 360,
    columnWidthRatio: 0.72,
    tooltip: {
      title: (datum) => datum?.month,
      items: [
        { field: 'average_return', name: 'Avg Return', valueFormatter: formatSignedPercent },
      ],
    },
    axis: {
      y: {
        title: 'Average return %',
      },
    },
  };

  const selectedMonthConfig = {
    data: selectedMonthChartData,
    xField: 'year',
    yField: 'return_percent',
    height: 360,
    columnWidthRatio: 0.6,
    tooltip: {
      items: [
        { field: 'return_percent', name: 'Return', valueFormatter: formatSignedPercent },
      ],
    },
    axis: {
      y: { title: `${MONTHS[selectedMonth - 1]} return %` },
    },
  };

  const yearlyConfig = {
    data: yearlyChartData,
    xField: 'year',
    yField: 'return_percent',
    height: 360,
    point: true,
    tooltip: {
      items: [
        { field: 'return_percent', name: 'Return', valueFormatter: formatSignedPercent },
      ],
    },
    axis: {
      y: { title: 'Return %' },
    },
  };

  const columns = [
    {
      title: 'Year',
      dataIndex: 'year',
      key: 'year',
    },
    {
      title: 'Return',
      dataIndex: 'return_percent',
      key: 'return_percent',
      sorter: (left, right) => Number(left.return_percent || 0) - Number(right.return_percent || 0),
      render: (value) => <Text className={valueClassName(value)}>{formatSignedPercent(value)}</Text>,
    },
  ];

  return (
    <Sidebar>
      <div className="seasonality-page">
        <Space direction="vertical" size={4}>
          <Title level={2} style={{ marginBottom: 0 }}>
            {selectedAsset} Seasonality Analysis
          </Title>
          <Text type="secondary">
            Select a month to focus the chart and history on that season for this asset.
          </Text>
        </Space>

        <Card style={{ marginTop: 18 }}>
          <div className="seasonality-toolbar">
            <div className="seasonality-control-group">
              <Select
                className="seasonality-select"
                value={years}
                onChange={setYears}
                options={[
                  { label: 'Last 5 years', value: 5 },
                  { label: 'Last 10 years', value: 10 },
                  { label: 'Last 15 years', value: 15 },
                  { label: 'Last 20 years', value: 20 },
                ]}
              />
              <Select
                className="seasonality-select"
                value={selectedMonth}
                onChange={setSelectedMonth}
                options={MONTHS.map((month, index) => ({
                  label: month,
                  value: index + 1,
                }))}
              />
            </div>

            <Button
              icon={<ReloadOutlined />}
              loading={loading}
              onClick={() => fetchSeasonality(true)}
            >
              Refresh
            </Button>
          </div>
        </Card>

        {error && (
          <Alert
            type="error"
            showIcon
            style={{ marginTop: 16 }}
            message="Seasonality data is unavailable"
            description={error}
          />
        )}

        <Spin spinning={loading}>
          {payload ? (
            <>
              <Row gutter={[16, 16]} className="seasonality-summary-grid">
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic title="Asset" value={selectedItem?.asset_symbol || selectedAsset} />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic title="Lookback Window" value={`${payload.meta?.years || years} years`} />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card>
                    <Statistic
                      title={`${MONTHS[selectedMonth - 1]} Average`}
                      value={formatSignedPercent(selectedMonthData?.average_return)}
                    />
                  </Card>
                </Col>
              </Row>

              <Card
                className="seasonality-chart-card"
                title={`${MONTHS[selectedMonth - 1]} Returns by Year`}
                extra={
                  <Space>
                    {selectedMonthData?.best_year && (
                      <Tag color="green">
                        Best {selectedMonthData.best_year.year}:{' '}
                        {formatSignedPercent(selectedMonthData.best_year.return_percent)}
                      </Tag>
                    )}
                    {selectedMonthData?.worst_year && (
                      <Tag color="red">
                        Worst {selectedMonthData.worst_year.year}:{' '}
                        {formatSignedPercent(selectedMonthData.worst_year.return_percent)}
                      </Tag>
                    )}
                  </Space>
                }
              >
                {selectedMonthChartData.length ? <Column {...selectedMonthConfig} /> : <Empty />}
              </Card>

              <Card
                className="seasonality-chart-card"
                title="All Months Average Return"
              >
                {monthlyChartData.length ? <Column {...monthlyConfig} /> : <Empty />}
              </Card>

              <Card className="seasonality-chart-card" title="Yearly Return">
                {yearlyChartData.length ? <Line {...yearlyConfig} /> : <Empty />}
              </Card>

              <Card
                className="seasonality-month-table"
                title={`${MONTHS[selectedMonth - 1]} History`}
              >
                <Table
                  rowKey="year"
                  columns={columns}
                  dataSource={monthHistoryRows}
                  pagination={false}
                  scroll={{ x: true }}
                />
              </Card>
            </>
          ) : (
            !loading && <Empty style={{ marginTop: 30 }} />
          )}
        </Spin>
      </div>
    </Sidebar>
  );
};

export default SeasonalityAnalysis;
