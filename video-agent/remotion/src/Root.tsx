import React from 'react';
import {Composition} from 'remotion';
import scenes from '../public/scenes.json';
import {StoryVideo} from './StoryVideo';

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="StoryVideo"
      component={StoryVideo}
      durationInFrames={scenes.scene_count * scenes.scene_frames}
      fps={scenes.fps ?? 30}
      width={scenes.video_w ?? 1920}
      height={scenes.video_h ?? 1080}
    />
  );
};