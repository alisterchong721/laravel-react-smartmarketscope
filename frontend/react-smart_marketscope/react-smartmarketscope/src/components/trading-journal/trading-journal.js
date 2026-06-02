import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import Sidebar from '../sidebar';
import {
  fetchTradesRequest,
  createTradeRequest,
  updateTradeRequest,
  deleteTradeRequest,
  resetSuccessState,
} from '../../actions/tradingJounalActions';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  message,
  Card,
  Row,
  Col,
  Tag,
  Space,
  Tabs,
  Typography,
  Popconfirm,
  Tooltip,
  Grid,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import moment from 'moment';
import {
  buildTradeSubmitPayload,
  convertToDayjs,
  prepareJournalDateForInput,
} from './trading-journal-utils';

const { Title, Text } = Typography;
const { Option } = Select;
const { TextArea } = Input;

const LEGACY_DIRECTION_MAP = {
  LONG: 'BUY',
  SHORT: 'SELL',
};

const normalizeDirection = (direction) => {
  const normalized = direction?.toString().toUpperCase();
  return LEGACY_DIRECTION_MAP[normalized] || normalized;
};

const decimalPricePattern = /^\d+(\.\d+)?$/;
const decimalProfitLossPattern = /^-?\d+(\.\d+)?$/;
const allowedPriceControlKeys = new Set([
  'Backspace',
  'Delete',
  'Tab',
  'Escape',
  'Enter',
  'ArrowLeft',
  'ArrowRight',
  'ArrowUp',
  'ArrowDown',
  'Home',
  'End',
]);

const isValidPriceValue = (value) => {
  if (value === null || value === undefined || value === '') return true;
  const textValue = value.toString();
  return decimalPricePattern.test(textValue) && Number(textValue) > 0;
};

const isValidProfitLossValue = (value) => {
  if (value === null || value === undefined || value === '') return true;
  return decimalProfitLossPattern.test(value.toString());
};

const getPriceValidationRules = (isRequired = false) => [
  ...(isRequired ? [{ required: true, message: 'Please enter a price' }] : []),
  {
    validator: (_, value) =>
      isValidPriceValue(value)
        ? Promise.resolve()
        : Promise.reject(
            new Error('Use numbers or decimals only, e.g. 1.2345')
          ),
  },
];

const getProfitLossValidationRules = () => [
  {
    validator: (_, value) =>
      isValidProfitLossValue(value)
        ? Promise.resolve()
        : Promise.reject(
            new Error('Use numbers or decimals only, e.g. -12.50')
          ),
  },
];

const getDecimalInputProps = ({ allowNegative = false } = {}) => ({
  min: 0,
  precision: 5,
  controls: false,
  style: { width: '100%' },
  inputMode: 'decimal',
  onKeyDown: (event) => {
    const { key, currentTarget } = event;

    if (
      allowedPriceControlKeys.has(key) ||
      ((event.metaKey || event.ctrlKey) &&
        ['a', 'c', 'v', 'x'].includes(key.toLowerCase()))
    ) {
      return;
    }

    if (/^\d$/.test(key)) return;

    if (key === '.' && !currentTarget.value.includes('.')) return;

    if (
      allowNegative &&
      key === '-' &&
      currentTarget.selectionStart === 0 &&
      !currentTarget.value.includes('-')
    ) {
      return;
    }

    event.preventDefault();
  },
  onPaste: (event) => {
    const pastedText = event.clipboardData.getData('text').trim();
    const validPattern = allowNegative
      ? decimalProfitLossPattern
      : decimalPricePattern;

    if (!validPattern.test(pastedText)) {
      event.preventDefault();
    }
  },
});

const getPriceInputProps = () => getDecimalInputProps();

const getProfitLossInputProps = () => ({
  ...getDecimalInputProps({ allowNegative: true }),
  min: undefined,
  precision: 2,
});

const formatPrice = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  const price = Number(value);
  if (!Number.isFinite(price)) return '-';
  return price.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 5,
  });
};

const parseProfitLoss = (value) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
};

const formatMoney = (value) => {
  const numericValue = parseProfitLoss(value);

  if (numericValue === null) {
    return '-';
  }

  const absoluteValue = Math.abs(numericValue).toFixed(2);
  return `${numericValue < 0 ? '-' : '+'}$${absoluteValue}`;
};

const TradingJournal = () => {
  const { useBreakpoint } = Grid;
  const screens = useBreakpoint();
  const dispatch = useDispatch();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const tradingJournalState = useSelector((state) => state.tradingJournal);
  const {
    trades = [],
    loading = false,
    error = null,
    success = false,
  } = tradingJournalState;

  const [isModalVisible, setIsModalVisible] = useState(false);
  const [editingTrade, setEditingTrade] = useState(null);
  const [searchText, setSearchText] = useState('');
  const [exitTimeError, setExitTimeError] = useState('');
  const [entryTimeValue, setEntryTimeValue] = useState(null);
  const [exitTimeValue, setExitTimeValue] = useState(null);
  const [dateFieldsTouched, setDateFieldsTouched] = useState({
    entry_time: false,
    exit_time: false,
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    dispatch(fetchTradesRequest());
  }, [dispatch]);

  // FIXED SUCCESS LOGIC
  useEffect(() => {
    if (success) {
      // ONLY close the modal if the success came from a Create/Update (isSubmitting)
      if (isModalVisible && isSubmitting) {
        const msg = editingTrade
          ? 'Trade updated successfully!'
          : 'Trade created successfully!';
        messageApi.success(msg);
        handleCancel(); // This resets isSubmitting to false
      } else if (!isModalVisible) {
        // If success came from Delete (modal is closed), just show message
        // You can add messageApi.success('Trade deleted') in handleDelete instead if preferred
        dispatch(resetSuccessState());
      }
    }

    if (error) {
      messageApi.error(error);
      setIsSubmitting(false);
      dispatch(resetSuccessState());
    }
  }, [success, error, isModalVisible, isSubmitting]);

  const formatTableDate = (date) => {
    if (!date) return '-';
    // Display in Malaysia Time (GMT+8)
    return moment
      .utc(date)
      .utcOffset(8)
      .format(screens.xs ? 'DD/MM HH:mm' : 'DD/MM/YY HH:mm');
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    setEditingTrade(null);
    setExitTimeError('');
    setEntryTimeValue(null);
    setExitTimeValue(null);
    setDateFieldsTouched({ entry_time: false, exit_time: false });
    setIsSubmitting(false);
    form.resetFields();
    dispatch(resetSuccessState()); // Clear Redux state on close
  };

  const showModal = () => {
    dispatch(resetSuccessState()); // CRITICAL: Clear success flag BEFORE opening
    setEditingTrade(null);
    setExitTimeError('');
    setEntryTimeValue(null);
    setExitTimeValue(null);
    setDateFieldsTouched({ entry_time: false, exit_time: false });
    form.resetFields();
    setIsModalVisible(true);
  };

  const handleEdit = (trade) => {
    dispatch(resetSuccessState()); // CRITICAL: Clear success flag BEFORE opening
    setEditingTrade(trade);
    setExitTimeError('');
    form.resetFields();
    setEntryTimeValue(prepareJournalDateForInput(trade.entry_time));
    setExitTimeValue(prepareJournalDateForInput(trade.exit_time));
    setDateFieldsTouched({ entry_time: false, exit_time: false });

    form.setFieldsValue({
      ...trade,
      direction: normalizeDirection(trade.direction),
      entry_price: parseFloat(trade.entry_price),
      exit_price: trade.exit_price ? parseFloat(trade.exit_price) : undefined,
      profit_loss: trade.profit_loss ? parseFloat(trade.profit_loss) : undefined,
    });

    setIsModalVisible(true);
  };

  const handleDelete = (tradeId) => {
    setIsSubmitting(false); // Ensure this is false so the modal logic doesn't trigger
    dispatch(deleteTradeRequest(tradeId));
    messageApi.success('Trade deleted successfully');
  };

  const validateExitTimeOnSubmit = () => {
    if (
      editingTrade &&
      !dateFieldsTouched.entry_time &&
      !dateFieldsTouched.exit_time
    ) {
      setExitTimeError('');
      return true;
    }

    const entry = entryTimeValue;
    const exit = exitTimeValue;

    if (!entry) {
      setExitTimeError('Entry time is required');
      return false;
    }
    if (!exit) return true;

    const start = convertToDayjs(entry)?.startOf('minute');
    const end = convertToDayjs(exit)?.startOf('minute');

    if (!start || !end) {
      setExitTimeError('Please select a valid date and time');
      return false;
    }

    const diffInMinutes = end.diff(start, 'minute');

    if (diffInMinutes < 1) {
      setExitTimeError('Exit must be at least 1 minute after entry');
      return false;
    }
    setExitTimeError('');
    return true;
  };

  const handleSubmit = async (values) => {
    if (!validateExitTimeOnSubmit()) return;

    try {
      setIsSubmitting(true); // "Lock" the success logic for form submission
      const formattedValues = buildTradeSubmitPayload({
        values,
        entryTimeValue,
        exitTimeValue,
        isEditing: Boolean(editingTrade),
        dateFieldsTouched,
      });

      if (editingTrade) {
        dispatch(updateTradeRequest(editingTrade.trade_id, formattedValues));
      } else {
        dispatch(createTradeRequest(formattedValues));
      }
    } catch (err) {
      setIsSubmitting(false);
      messageApi.error('An unexpected error occurred');
    }
  };

  const columns = [
    {
      title: 'Asset',
      dataIndex: 'asset_symbol',
      key: 'asset_symbol',
      render: (text) => <strong>{text?.toUpperCase()}</strong>,
      width: screens.xs ? 80 : 100,
    },
    {
      title: 'Direction',
      dataIndex: 'direction',
      key: 'direction',
      render: (dir) => (
        <Tag color={normalizeDirection(dir) === 'BUY' ? 'green' : 'red'}>
          {normalizeDirection(dir)}
        </Tag>
      ),
      width: 90,
    },
    {
      title: 'Entry Time (MYT)',
      dataIndex: 'entry_time',
      key: 'entry_time',
      render: (date) => formatTableDate(date),
      width: 150,
    },
    {
      title: 'Entry Price',
      dataIndex: 'entry_price',
      key: 'entry_price',
      render: (value) => formatPrice(value),
      width: 120,
    },
    {
      title: 'Exit Time (MYT)',
      dataIndex: 'exit_time',
      key: 'exit_time',
      render: (date) => formatTableDate(date),
      width: 150,
    },
    {
      title: 'Exit Price',
      dataIndex: 'exit_price',
      key: 'exit_price',
      render: (value) => formatPrice(value),
      width: 120,
    },
    {
      title: 'P/L',
      dataIndex: 'profit_loss',
      key: 'profit_loss',
      // align: 'right',
      render: (val) => {
        if (val === null || val === undefined) return '-';
        const num = parseFloat(val);
        return (
          <Text strong style={{ color: num >= 0 ? 'green' : 'red' }}>
            {formatMoney(num)}
          </Text>
        );
      },
      width: 100,
    },
    {
      title: 'Notes',
      dataIndex: 'notes',
      key: 'notes',
      ellipsis: true, // This keeps the table neat if the note is long
      render: (text) => (
        <Tooltip title={text}>
          <span>{text || '-'}</span>
        </Tooltip>
      ),
      width: 200,
    },
    {
      title: 'Action',
      key: 'action',
      align: 'center',
      render: (_, record) => (
        <Space size="middle">
          <Tooltip title="Edit">
            <Button
              type="link"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="Delete trade?"
            onConfirm={() => handleDelete(record.trade_id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
      width: 100,
    },
  ];

  const filteredTrades = trades.filter((trade) => {
    const searchLower = searchText.toLowerCase();
    return (
      trade.asset_symbol?.toLowerCase().includes(searchLower) ||
      trade.direction?.toLowerCase().includes(searchLower)
    );
  });

  const dashboardStats = useMemo(() => {
    const closedTrades = trades
      .map((trade) => ({
        ...trade,
        normalizedDirection: normalizeDirection(trade.direction),
        profitLossValue: parseProfitLoss(trade.profit_loss),
      }))
      .filter((trade) => trade.profitLossValue !== null);

    const winningTrades = closedTrades.filter((trade) => trade.profitLossValue > 0);
    const losingTrades = closedTrades.filter((trade) => trade.profitLossValue < 0);
    const grossProfit = winningTrades.reduce(
      (total, trade) => total + trade.profitLossValue,
      0
    );
    const grossLoss = losingTrades.reduce(
      (total, trade) => total + trade.profitLossValue,
      0
    );
    const totalProfitLoss = closedTrades.reduce(
      (total, trade) => total + trade.profitLossValue,
      0
    );

    const bestTrade = [...closedTrades].sort(
      (left, right) => right.profitLossValue - left.profitLossValue
    )[0];
    const worstTrade = [...closedTrades].sort(
      (left, right) => left.profitLossValue - right.profitLossValue
    )[0];

    const aggregateBy = (keySelector) =>
      Object.values(
        closedTrades.reduce((groups, trade) => {
          const key = keySelector(trade) || 'Unknown';

          if (!groups[key]) {
            groups[key] = {
              key,
              label: key,
              trades: 0,
              wins: 0,
              losses: 0,
              profitLoss: 0,
            };
          }

          groups[key].trades += 1;
          groups[key].wins += trade.profitLossValue > 0 ? 1 : 0;
          groups[key].losses += trade.profitLossValue < 0 ? 1 : 0;
          groups[key].profitLoss += trade.profitLossValue;

          return groups;
        }, {})
      ).sort((left, right) => right.profitLoss - left.profitLoss);

    return {
      totalTrades: trades.length,
      closedTrades: closedTrades.length,
      openTrades: trades.length - closedTrades.length,
      winningTrades: winningTrades.length,
      losingTrades: losingTrades.length,
      grossProfit,
      grossLoss,
      totalProfitLoss,
      averageProfitLoss: closedTrades.length ? totalProfitLoss / closedTrades.length : 0,
      winRate: closedTrades.length
        ? (winningTrades.length / closedTrades.length) * 100
        : 0,
      profitFactor:
        grossLoss < 0 ? grossProfit / Math.abs(grossLoss) : grossProfit > 0 ? Infinity : 0,
      bestTrade,
      worstTrade,
      byAsset: aggregateBy((trade) => trade.asset_symbol?.toUpperCase()),
      byDirection: aggregateBy((trade) => trade.normalizedDirection),
    };
  }, [trades]);

  const dashboardMetricCards = [
    {
      title: 'Net P/L',
      value: formatMoney(dashboardStats.totalProfitLoss),
      color: dashboardStats.totalProfitLoss >= 0 ? 'green' : 'red',
    },
    {
      title: 'Win Rate',
      value: `${dashboardStats.winRate.toFixed(1)}%`,
      color: dashboardStats.winRate >= 50 ? 'green' : 'red',
    },
    {
      title: 'Closed Trades',
      value: dashboardStats.closedTrades,
      color: '#1677ff',
    },
    {
      title: 'Average P/L',
      value: formatMoney(dashboardStats.averageProfitLoss),
      color: dashboardStats.averageProfitLoss >= 0 ? 'green' : 'red',
    },
    {
      title: 'Profit Factor',
      value:
        dashboardStats.profitFactor === Infinity
          ? 'Perfect'
          : dashboardStats.profitFactor.toFixed(2),
      color: dashboardStats.profitFactor >= 1 ? 'green' : 'red',
    },
    {
      title: 'Open Trades',
      value: dashboardStats.openTrades,
      color: '#595959',
    },
  ];

  const performanceColumns = [
    {
      title: 'Group',
      dataIndex: 'label',
      key: 'label',
      render: (value) => <Text strong>{value}</Text>,
    },
    {
      title: 'Trades',
      dataIndex: 'trades',
      key: 'trades',
    },
    {
      title: 'Wins / Losses',
      key: 'wins_losses',
      render: (_, record) => `${record.wins} / ${record.losses}`,
    },
    {
      title: 'P/L',
      dataIndex: 'profitLoss',
      key: 'profitLoss',
      render: (value) => (
        <Text strong style={{ color: Number(value) >= 0 ? 'green' : 'red' }}>
          {formatMoney(value)}
        </Text>
      ),
    },
  ];

  const resultMixItems = [
    {
      label: 'Wins',
      value: dashboardStats.winningTrades,
      amountLabel: 'Gross Profit',
      amount: dashboardStats.grossProfit,
      percent: dashboardStats.winningTrades + dashboardStats.losingTrades
        ? (dashboardStats.winningTrades /
            (dashboardStats.winningTrades + dashboardStats.losingTrades)) *
          100
        : 0,
      color: 'green',
    },
    {
      label: 'Losses',
      value: dashboardStats.losingTrades,
      amountLabel: 'Gross Loss',
      amount: dashboardStats.grossLoss,
      percent: dashboardStats.winningTrades + dashboardStats.losingTrades
        ? (dashboardStats.losingTrades /
            (dashboardStats.winningTrades + dashboardStats.losingTrades)) *
          100
        : 0,
      color: 'red',
    },
  ];

  const dashboardContent = (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={[16, 16]}>
        {dashboardMetricCards.map((metric) => (
          <Col xs={24} sm={12} lg={8} xl={4} key={metric.title}>
            <Card>
              <Text type="secondary">{metric.title}</Text>
              <Title level={4} style={{ margin: '8px 0 0', color: metric.color }}>
                {metric.value}
              </Title>
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} style={{ display: 'flex' }}>
          <Card title="Result Mix" style={{ width: '100%' }}>
            <Space
              direction="vertical"
              size="large"
              style={{ width: '100%' }}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: screens.xs
                    ? '1fr'
                    : 'repeat(2, minmax(220px, 1fr))',
                  gap: 16,
                }}
              >
                {resultMixItems.map((item) => (
                  <div
                    key={item.label}
                    style={{
                      padding: '16px 18px',
                      border: '1px solid #f0f0f0',
                      borderLeft: `4px solid ${item.color}`,
                      borderRadius: 8,
                      background: '#fafafa',
                    }}
                  >
                    <Text type="secondary">{item.label}</Text>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'baseline',
                        gap: 12,
                        marginTop: 4,
                      }}
                    >
                      <Title
                        level={3}
                        style={{ color: item.color, margin: 0 }}
                      >
                        {item.value}
                      </Title>
                      <Text strong style={{ color: item.color }}>
                        {item.percent.toFixed(1)}%
                      </Text>
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <Text type="secondary">{item.amountLabel}</Text>
                      <br />
                      <Text strong style={{ color: item.color }}>
                        {formatMoney(item.amount)}
                      </Text>
                    </div>
                  </div>
                ))}
              </div>

              <div
                style={{
                  display: 'flex',
                  height: 10,
                  overflow: 'hidden',
                  borderRadius: 999,
                  background: '#f0f0f0',
                }}
              >
                {resultMixItems.map((item) => (
                  <div
                    key={item.label}
                    style={{
                      width: `${item.percent}%`,
                      minWidth: item.value > 0 ? 8 : 0,
                      background: item.color,
                    }}
                  />
                ))}
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Performance by Asset" bodyStyle={{ padding: 0 }}>
            <Table
              rowKey="key"
              columns={performanceColumns}
              dataSource={dashboardStats.byAsset}
              pagination={false}
              size="middle"
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="Performance by Direction" bodyStyle={{ padding: 0 }}>
            <Table
              rowKey="key"
              columns={performanceColumns}
              dataSource={dashboardStats.byDirection}
              pagination={false}
              size="middle"
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );

  const tradesContent = (
    <Card bodyStyle={{ padding: 0 }}>
      <Table
        columns={columns}
        dataSource={filteredTrades}
        rowKey="trade_id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1040 }}
      />
    </Card>
  );

  return (
    <>
      {contextHolder}
      <Sidebar>
        <div style={{ padding: screens.xs ? '10px' : '20px' }}>
          <Row
            justify="space-between"
            align="middle"
            gutter={[16, 16]}
            style={{ marginBottom: 20 }}
          >
            <Col xs={24} md={11} lg={10}>
              <Title level={2} style={{ margin: 0 }}>
                Trading Journal
              </Title>
            </Col>
            <Col
              xs={24}
              md={13}
              lg={14}
              style={{ textAlign: screens.xs ? 'left' : 'right' }}
            >
              <Space wrap>
                <Input
                  placeholder="Search..."
                  prefix={<SearchOutlined />}
                  onChange={(e) => setSearchText(e.target.value)}
                />
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={showModal}
                >
                  Add Trade
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => dispatch(fetchTradesRequest())}
                />
              </Space>
            </Col>
          </Row>

          <Tabs
            defaultActiveKey="dashboard"
            items={[
              {
                key: 'dashboard',
                label: 'Dashboard',
                children: dashboardContent,
              },
              {
                key: 'trades',
                label: 'Trades',
                children: tradesContent,
              },
            ]}
          />

          <Modal
            title={editingTrade ? 'Edit Trade' : 'Add New Trade'}
            open={isModalVisible}
            onCancel={handleCancel}
            footer={null}
            width={700}
            destroyOnClose
          >
            <Form form={form} layout="vertical" onFinish={handleSubmit}>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="asset_symbol"
                    label="Asset"
                    rules={[{ required: true }]}
                  >
                    <Input placeholder="e.g. EURUSD" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    name="direction"
                    label="Direction"
                    rules={[{ required: true }]}
                  >
                    <Select placeholder="Select Direction">
                      <Option value="BUY">BUY</Option>
                      <Option value="SELL">SELL</Option>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    label="Entry Time (MYT)"
                    required
                    validateStatus={!entryTimeValue && exitTimeError ? 'error' : ''}
                    help={!entryTimeValue && exitTimeError ? exitTimeError : ''}
                  >
                    <Input
                      type="datetime-local"
                      value={entryTimeValue}
                      onChange={(event) => {
                        setEntryTimeValue(event.target.value);
                        setDateFieldsTouched((current) => ({
                          ...current,
                          entry_time: true,
                        }));
                        setExitTimeError('');
                      }}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item
                    label="Exit Time (MYT)"
                    validateStatus={exitTimeError ? 'error' : ''}
                    help={exitTimeError}
                  >
                    <Input
                      type="datetime-local"
                      value={exitTimeValue}
                      onChange={(event) => {
                        setExitTimeValue(event.target.value);
                        setDateFieldsTouched((current) => ({
                          ...current,
                          exit_time: true,
                        }));
                        setExitTimeError('');
                      }}
                      style={{ width: '100%' }}
                    />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item
                    name="entry_price"
                    label="Entry Price"
                    rules={getPriceValidationRules(true)}
                  >
                    <InputNumber {...getPriceInputProps()} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="exit_price"
                    label="Exit Price"
                    rules={getPriceValidationRules()}
                  >
                    <InputNumber {...getPriceInputProps()} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="profit_loss"
                    label="Profit/Loss ($)"
                    rules={getProfitLossValidationRules()}
                  >
                    <InputNumber {...getProfitLossInputProps()} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item name="notes" label="Notes">
                <TextArea rows={3} placeholder="Strategy details..." />
              </Form.Item>

              <div style={{ textAlign: 'right', marginTop: 20 }}>
                <Space>
                  <Button onClick={handleCancel}>Cancel</Button>
                  <Button
                    type="primary"
                    htmlType="submit"
                    loading={isSubmitting}
                  >
                    {editingTrade ? 'Update Trade' : 'Create Trade'}
                  </Button>
                </Space>
              </div>
            </Form>
          </Modal>
        </div>
      </Sidebar>
    </>
  );
};

export default TradingJournal;
