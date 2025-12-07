import { randomInt } from "crypto";

const ALPHANUM = "abcdefghjkmnpqrstuvwxyz23456789";
const CHARSET = `${ALPHANUM}-`;
const MIN_LENGTH = 5;
const MAX_LENGTH = 10;

// No leading/trailing dashes, no repeated dashes, only safe chars, length 1-10.
export const slugRegex =
  /^(?!.*--)(?!.*-$)[a-hj-km-np-z2-9](?:[a-hj-km-np-z2-9-]{0,8}[a-hj-km-np-z2-9])?$/;

export function isValidSlug(slug: string): boolean {
  return slugRegex.test(slug);
}

function pickChar(options: { isFirst: boolean; isLast: boolean; prevDash: boolean }): string {
  for (let i = 0; i < 50; i += 1) {
    const char = CHARSET[randomInt(0, CHARSET.length)];
    if ((options.isFirst || options.isLast) && char === "-") {
      continue;
    }
    if (options.prevDash && char === "-") {
      continue;
    }
    return char;
  }
  // Extremely unlikely fallback.
  return "a";
}

export function generateSlug(): string {
  const length = randomInt(MIN_LENGTH, MAX_LENGTH + 1);
  let slug = "";
  for (let i = 0; i < length; i += 1) {
    const isFirst = i === 0;
    const isLast = i === length - 1;
    const char = pickChar({ isFirst, isLast, prevDash: slug.endsWith("-") });
    slug += char;
  }

  if (!isValidSlug(slug)) {
    // Extremely unlikely, but regenerate if validation fails.
    return generateSlug();
  }

  return slug;
}
