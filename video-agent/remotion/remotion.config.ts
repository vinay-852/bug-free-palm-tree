import {Config} from '@remotion/cli/config';

// .svg imports become raw strings (webpack asset/source module), so the
// storyboard in public/story.svg is a webpack module: editing it
// invalidates the bundle cache automatically, and re-rendering picks up
// the change.
Config.overrideWebpackConfig((config) => {
  return {
    ...config,
    module: {
      ...config.module,
      rules: [
        {
          test: /\.svg$/,
          type: 'asset/source',
        },
        ...(config.module?.rules ?? []),
      ],
    },
  };
});