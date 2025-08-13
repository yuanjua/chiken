import {getRequestConfig} from 'next-intl/server';

export default getRequestConfig(async ({locale}) => {
  const supported = ['en', 'zh'] as const;
  const resolved: 'en' | 'zh' = (supported as readonly string[]).includes(locale || '')
    ? (locale as 'en' | 'zh')
    : 'en';

  const messages = (await import(`../messages/${resolved}.json`)).default;
  return {messages, locale: resolved};
});


