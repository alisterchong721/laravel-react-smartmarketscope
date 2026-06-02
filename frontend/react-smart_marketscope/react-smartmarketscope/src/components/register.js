import React, { useEffect, useState, useRef } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  registerRequest,
  resendRegisterCodeRequest,
  resetAuthState,
  verifyRegisterRequest,
} from '../actions/authActions';
import { useNavigate } from 'react-router-dom';
import { Row, Col, Input, Card, Button, Form, message, Typography, Space } from 'antd';
import { Link } from 'react-router-dom';

const { Text, Paragraph } = Typography;

const Register = () => {
  const dispatch = useDispatch();
  const {
    loading,
    error,
    isAuthenticated,
    registrationVerificationSent,
    pendingRegistrationEmail,
    lastRegistrationAction,
    resendCooldownSeconds,
  } = useSelector((state) => state.auth);
  const navigate = useNavigate();
  const [registerForm] = Form.useForm();
  const [verifyForm] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitAction, setSubmitAction] = useState(null);
  const [submittedEmail, setSubmittedEmail] = useState('');
  const [resendSeconds, setResendSeconds] = useState(0);
  const hasRedirected = useRef(false);
  const verificationEmail = pendingRegistrationEmail || submittedEmail;

  const formatCooldown = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = String(seconds % 60).padStart(2, '0');

    return `${minutes}:${remainingSeconds}`;
  };

  useEffect(() => {
    if (dispatch && resetAuthState) {
      dispatch(resetAuthState());
    }
  }, [dispatch]);

  // 1. Handle Errors
  useEffect(() => {
    if (error) {
      messageApi.error(error.message || error || 'Registration failed');
      setIsSubmitting(false);
      setSubmitAction(null);
    }
  }, [error, messageApi]);

  // 2. Handle Success
  useEffect(() => {
    if (
      registrationVerificationSent &&
      isSubmitting &&
      submitAction === lastRegistrationAction &&
      !hasRedirected.current
    ) {
      if (submitAction === 'resend') {
        messageApi.success('Verification code sent again. Please wait 5 minutes before resending.');
      } else {
        messageApi.success('Verification code sent to your email.');
      }

      setIsSubmitting(false);
      setSubmitAction(null);
    }
  }, [
    registrationVerificationSent,
    messageApi,
    isSubmitting,
    submitAction,
    lastRegistrationAction,
  ]);

  useEffect(() => {
    if (resendCooldownSeconds > 0) {
      setResendSeconds(resendCooldownSeconds);
    }
  }, [resendCooldownSeconds, lastRegistrationAction]);

  useEffect(() => {
    if (resendSeconds <= 0) {
      return undefined;
    }

    const timer = setInterval(() => {
      setResendSeconds((currentSeconds) => Math.max(0, currentSeconds - 1));
    }, 1000);

    return () => clearInterval(timer);
  }, [resendSeconds]);

  useEffect(() => {
    if (
      isAuthenticated &&
      isSubmitting &&
      submitAction === 'verify' &&
      !hasRedirected.current
    ) {
      hasRedirected.current = true;

      messageApi.success('Account verified. Redirecting...');

      const timer = setTimeout(() => {
        navigate('/overview');
      }, 1500);

      return () => clearTimeout(timer);
    }
  }, [isAuthenticated, navigate, messageApi, isSubmitting, submitAction]);

  const handleFormSubmit = (values) => {
    setIsSubmitting(true);
    setSubmitAction('register');
    setSubmittedEmail(values.email);
    hasRedirected.current = false; // Reset ref on new click
    dispatch(
      registerRequest({
        email: values.email,
        password: values.password,
        password_confirmation: values.confirmPassword,
      })
    );
  };

  const handleVerificationSubmit = (values) => {
    setIsSubmitting(true);
    setSubmitAction('verify');
    hasRedirected.current = false;
    dispatch(
      verifyRegisterRequest({
        email: verificationEmail,
        code: values.code,
      })
    );
  };

  const handleResendCode = () => {
    if (resendSeconds > 0) {
      messageApi.info(
        `Verification code already sent. Please wait ${formatCooldown(resendSeconds)} before resending.`
      );
      return;
    }

    setIsSubmitting(true);
    setSubmitAction('resend');
    dispatch(
      resendRegisterCodeRequest({
        email: verificationEmail,
      })
    );
  };

  const handleUseDifferentEmail = () => {
    setIsSubmitting(false);
    setSubmitAction(null);
    setSubmittedEmail('');
    setResendSeconds(0);
    verifyForm.resetFields();
    dispatch(resetAuthState());
  };

  return (
    <>
      {contextHolder}
      <Row justify={'center'} align={'middle'} style={{ minHeight: '100vh' }}>
        <Col xs={22} sm={15} md={11} lg={9} xl={7}>
          <Card
            title={registrationVerificationSent ? 'Verify Email' : 'Sign Up'}
            style={{ textAlign: 'center' }}
          >
            {!registrationVerificationSent ? (
              <Form form={registerForm} layout="vertical" onFinish={handleFormSubmit}>
                <Form.Item
                  label="Email"
                  name="email"
                  rules={[
                    { required: true, message: 'Please input your email' },
                    {
                      pattern: /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/,
                      message: 'Please enter a valid email format',
                    },
                  ]}
                >
                  <Input placeholder="Enter your email" disabled={loading} />
                </Form.Item>

                <Form.Item
                  label="Password"
                  name="password"
                  rules={[
                    { required: true, message: 'Please input your password' },
                    { min: 8, message: 'Minimum 8 characters' },
                    {
                      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/,
                      message: 'Include uppercase, lowercase, and a number',
                    },
                  ]}
                  hasFeedback
                >
                  <Input.Password
                    placeholder="Enter your password"
                    disabled={loading}
                  />
                </Form.Item>

                <Form.Item
                  label="Confirm Password"
                  name="confirmPassword"
                  dependencies={['password']}
                  rules={[
                    { required: true, message: 'Please confirm your password' },
                    ({ getFieldValue }) => ({
                      validator(_, value) {
                        if (!value || getFieldValue('password') === value) {
                          return Promise.resolve();
                        }
                        return Promise.reject(
                          new Error('Passwords do not match!')
                        );
                      },
                    }),
                  ]}
                  hasFeedback
                >
                  <Input.Password
                    placeholder="Confirm your password"
                    disabled={loading}
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
                    Send Verification Code
                  </Button>

                  <div style={{ marginTop: '20px', textAlign: 'center' }}>
                    <Text>Already have an account? </Text>
                    <Link to="/login">Login Now</Link>
                  </div>
                </Form.Item>
              </Form>
            ) : (
              <Form form={verifyForm} layout="vertical" onFinish={handleVerificationSubmit}>
                <Paragraph style={{ marginBottom: 24 }}>
                  Enter the 6-digit code sent to <Text strong>{verificationEmail}</Text>.
                </Paragraph>

                <Form.Item
                  label="Verification Code"
                  name="code"
                  rules={[
                    { required: true, message: 'Please input your verification code' },
                    { pattern: /^\d{6}$/, message: 'Enter the 6-digit code' },
                  ]}
                >
                  <Input
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="123456"
                    disabled={loading || hasRedirected.current}
                    style={{
                      textAlign: 'center',
                      fontSize: 20,
                      letterSpacing: 6,
                    }}
                  />
                </Form.Item>

                <Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading || hasRedirected.current}
                    style={{
                      color: '#FFFFFF',
                      background: '#323030',
                    }}
                  >
                    {hasRedirected.current ? 'Redirecting...' : 'Verify and Create Account'}
                  </Button>
                </Form.Item>

                <Space direction="vertical" size={8}>
                  <Button
                    type="link"
                    onClick={handleResendCode}
                    disabled={loading}
                  >
                    {resendSeconds > 0
                      ? `Resend code in ${formatCooldown(resendSeconds)}`
                      : 'Resend code'}
                  </Button>
                  <Button type="link" onClick={handleUseDifferentEmail} disabled={loading}>
                    Use a different email
                  </Button>
                </Space>
              </Form>
            )}
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default Register;
