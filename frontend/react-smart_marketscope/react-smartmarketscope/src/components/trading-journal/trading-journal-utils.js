import dayjs from 'dayjs';
import moment from 'moment';

export const convertToDayjs = (value) => {
  if (!value) return null;

  if (dayjs.isDayjs(value)) {
    return value.isValid() ? value : null;
  }

  const parsed = dayjs(value);
  return parsed.isValid() ? parsed : null;
};

export const prepareJournalDateForInput = (dateValue) => {
  if (!dateValue) return '';

  const malaysiaTime = moment.utc(dateValue).utcOffset(8);
  if (!malaysiaTime.isValid()) return '';

  return malaysiaTime.format('YYYY-MM-DDTHH:mm');
};

export const prepareJournalDateForBackend = (dateValue) => {
  const date = convertToDayjs(dateValue);
  return date ? date.toISOString() : null;
};

export const buildTradeSubmitPayload = ({
  values,
  entryTimeValue,
  exitTimeValue,
  isEditing = false,
  dateFieldsTouched = { entry_time: false, exit_time: false },
}) => {
  const payload = {
    ...values,
    asset_symbol: values.asset_symbol?.toUpperCase(),
    profit_loss: values.profit_loss ?? null,
  };

  if (!isEditing || dateFieldsTouched.entry_time) {
    payload.entry_time = prepareJournalDateForBackend(entryTimeValue);
  }

  if (!isEditing || dateFieldsTouched.exit_time) {
    payload.exit_time = prepareJournalDateForBackend(exitTimeValue);
  }

  return payload;
};
