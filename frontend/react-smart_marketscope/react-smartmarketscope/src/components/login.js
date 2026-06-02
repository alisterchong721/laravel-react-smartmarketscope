import React, { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { loginRequest } from '../actions/authActions';
import { Row, Col, Input, Card, Button, Form, message, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';

const { Text } = Typography;

const Login = () => {
  const dispatch = useDispatch();
  const { loading, error, isAuthenticated } = useSelector(
    (state) => state.auth
  );
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const navigate = useNavigate();

  // Handle successful login with message and delayed redirect
  useEffect(() => {
    if (isAuthenticated) {
      // 1. Show the success message immediately
      messageApi.success('Login successful! Redirecting...');

      // 2. Wait 1.5 seconds so the user can actually see the popup
      const timer = setTimeout(() => {
        navigate('/overview');
      }, 1500);

      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, navigate, messageApi]);

  // Show error message if login fails
  useEffect(() => {
    if (error) {
      messageApi.error(error.message || error.error || 'Login failed');
    }
  }, [error, messageApi]);

  const handleFormSubmit = (values) => {
    console.log('🔍 Login form submitted with values:', values);
    dispatch(loginRequest(values));
  };

  return (
    <>
      {contextHolder}
      <Row justify={'center'} align={'middle'} style={{ minHeight: '100vh' }}>
        <Col xs={22} sm={15} md={11} lg={9} xl={7}>
          <Card
            title="Sign In"
            style={{
              textAlign: 'center',
              paddingBottom: '0',
            }}
          >
            <Form
              form={form}
              layout="vertical"
              onFinish={handleFormSubmit}
              autoComplete="off"
            >
              <Form.Item
                label="Email"
                name="email"
                rules={[
                  { required: true, message: 'Please input your email' },
                  { type: 'email', message: 'Please enter a valid email' },
                ]}
              >
                <Input placeholder="Enter your email" autoComplete="email" />
              </Form.Item>
              <Form.Item
                label="Password"
                name="password"
                rules={[
                  { required: true, message: 'Please input your password' },
                ]}
              >
                <Input.Password
                  placeholder="Enter your password"
                  autoComplete="current-password"
                />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  loading={loading}
                  style={{
                    color: '#FFFFFF',
                    background: '#323030',
                  }}
                >
                  Login Now
                </Button>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'center',
                    marginTop: '10px',
                  }}
                >
                  <Button
                    style={{ padding: '0' }}
                    type="link"
                    onClick={() => navigate('/forgot-password')}
                  >
                    Forgot your password?
                  </Button>
                </div>
                <div style={{ marginTop: '10px', textAlign: 'center' }}>
                  <Text>Not Registered? </Text>
                  <Link to="/register" style={{ marginLeft: '5px' }}>
                    Create an account
                  </Link>
                </div>
              </Form.Item>
            </Form>
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default Login;
