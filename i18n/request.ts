import {getRequestConfig} from 'next-intl/server';

export default getRequestConfig(async ({locale}) => {
  const supported = ['en', 'zh'] as const;
  const resolved: 'en' | 'zh' = (supported as readonly string[]).includes(locale || '')
    ? (locale as 'en' | 'zh')
    : 'en';

  const messages =
    resolved === 'en'
      ? (await import('../messages/en/index')).default
      : (await import('../messages/zh/index')).default;
  return {messages, locale: resolved};
});


