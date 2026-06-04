import React, { useState } from 'react';
import axios from 'axios';
import { Row, Col, Input, Card, Button, Form, message, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { apiPath } from '../config/api';

const { Text, Paragraph } = Typography;

const ForgotPassword = () => {
  const [emailForm] = Form.useForm();
  const [codeForm] = Form.useForm();
  const [passwordForm] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const navigate = useNavigate();
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const getErrorMessage = (error, fallback) =>
    error.response?.data?.message ||
    error.response?.data?.errors?.email?.[0] ||
    error.response?.data?.errors?.code?.[0] ||
    error.response?.data?.errors?.password?.[0] ||
    error.message ||
    fallback;

  const handleEmailSubmit = async (values) => {
    setLoading(true);

    try {
      const response = await axios.post(apiPath('/password/forgot'), {
        email: values.email,
      });

      setEmail(response.data.data?.email || values.email);
      setStep('code');
      messageApi.success('Password reset code sent to your email.');
    } catch (error) {
      messageApi.error(getErrorMessage(error, 'Unable to send reset code'));
    } finally {
      setLoading(false);
    }
  };

  const handleCodeSubmit = async (values) => {
    setLoading(true);

    try {
      await axios.post(apiPath('/password/validate-token'), {
        email,
        code: values.code,
      });

      setCode(values.code);
      setStep('password');
      messageApi.success('Code verified. Enter your new password.');
    } catch (error) {
      messageApi.error(getErrorMessage(error, 'Invalid or expired code'));
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (values) => {
    setLoading(true);

    try {
      await axios.post(apiPath('/password/reset'), {
        email,
        code,
        password: values.password,
        password_confirmation: values.confirmPassword,
      });

      messageApi.success('Password reset successfully. Redirecting...');
      setTimeout(() => navigate('/login'), 1200);
    } catch (error) {
      messageApi.error(getErrorMessage(error, 'Unable to reset password'));
    } finally {
      setLoading(false);
    }
  };

  const handleUseDifferentEmail = () => {
    setStep('email');
    setEmail('');
    setCode('');
    codeForm.resetFields();
    passwordForm.resetFields();
  };

  return (
    <>
      {contextHolder}
      <Row justify="center" align="middle" style={{ minHeight: '100vh' }}>
        <Col xs={22} sm={15} md={11} lg={9} xl={7}>
          <Card title="Reset Password" style={{ textAlign: 'center' }}>
            {step === 'email' && (
              <Form form={emailForm} layout="vertical" onFinish={handleEmailSubmit}>
                <Form.Item
                  label="Email"
                  name="email"
                  rules={[
                    { required: true, message: 'Please input your email' },
                    { type: 'email', message: 'Please enter a valid email' },
                  ]}
                >
                  <Input placeholder="Enter your registered email" disabled={loading} />
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading}
                    style={{ color: '#FFFFFF', background: '#323030' }}
                  >
                    Send Reset Code
                  </Button>
                  <div style={{ marginTop: 12 }}>
                    <Link to="/login">Back to login</Link>
                  </div>
                </Form.Item>
              </Form>
            )}

            {step === 'code' && (
              <Form form={codeForm} layout="vertical" onFinish={handleCodeSubmit}>
                <Paragraph style={{ marginBottom: 24 }}>
                  Enter the 6-digit code sent to <Text strong>{email}</Text>.
                </Paragraph>

                <Form.Item
                  label="Reset Code"
                  name="code"
                  rules={[
                    { required: true, message: 'Please input your reset code' },
                    { pattern: /^\d{6}$/, message: 'Enter the 6-digit code' },
                  ]}
                >
                  <Input
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="123456"
                    disabled={loading}
                    style={{ textAlign: 'center', fontSize: 20, letterSpacing: 6 }}
                  />
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading}
                    style={{ color: '#FFFFFF', background: '#323030' }}
                  >
                    Verify Code
                  </Button>
                  <Button type="link" onClick={handleUseDifferentEmail} disabled={loading}>
                    Use a different email
                  </Button>
                </Form.Item>
              </Form>
            )}

            {step === 'password' && (
              <Form form={passwordForm} layout="vertical" onFinish={handlePasswordSubmit}>
                <Form.Item
                  label="New Password"
                  name="password"
                  rules={[
                    { required: true, message: 'Please input your new password' },
                    { min: 8, message: 'Minimum 8 characters' },
                    {
                      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/,
                      message: 'Include uppercase, lowercase, and a number',
                    },
                  ]}
                  hasFeedback
                >
                  <Input.Password placeholder="Enter new password" disabled={loading} />
                </Form.Item>

                <Form.Item
                  label="Confirm New Password"
                  name="confirmPassword"
                  dependencies={['password']}
                  rules={[
                    { required: true, message: 'Please confirm your new password' },
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        if (!value || getFieldValue('password') === value) {
                          return Promise.resolve();
                        }
                        return Promise.reject(new Error('Passwords do not match!'));
                      },
                    }),
                  ]}
                  hasFeedback
                >
                  <Input.Password placeholder="Confirm new password" disabled={loading} />
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading}
                    style={{ color: '#FFFFFF', background: '#323030' }}
                  >
                    Reset Password
                  </Button>
                </Form.Item>
              </Form>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default ForgotPassword;
