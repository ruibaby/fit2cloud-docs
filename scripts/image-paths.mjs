// Markdown images are scoped by Rspress; literal MDX <img> tags need explicit paths.
export function scopeImagePaths(source, project) {
  return source.replace(
    /^([ \t]*)(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1\2[ \t]*(?:\n|$)|(`+)[^\n]*?\3|<img\b[^>]*>/gm,
    (token) =>
      token.startsWith("<img")
        ? token.replace(
            /(\bsrc\s*=\s*)(["'])(.*?)\2/g,
            (attribute, prefix, _quote, url) => {
              if (
                !url.startsWith("/img/") &&
                !url.startsWith(`/${project}/img/`)
              )
                return attribute;
              const scoped = url.startsWith("/img/")
                ? `/${project}${url}`
                : url;
              // Deployment URLs are not paths inside public/. Validate them in verify:build.
              return `${prefix}{${JSON.stringify(scoped)}}`;
            },
          )
        : token,
  );
}
