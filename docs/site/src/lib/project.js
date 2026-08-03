// Every off-site link the chrome needs, in one place. MDX pages can import these
// too, so a repo rename is one edit rather than a grep.
export const REPO_URL = 'https://github.com/IMIO/imio.emailkit'
export const PYPI_URL = 'https://pypi.org/project/imio.emailkit/'

/** A link to a file at the tip of the default branch. */
export function sourceUrl(path) {
  return `${REPO_URL}/blob/main/${path}`
}
