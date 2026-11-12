import { MATCH_TYPE_LABEL } from '../../constants/enums';

interface Props {
  matchType?: string;
  score?: number;
  conflicts?: number;
}

/** 映射命中分数徽标：精确 1.0 / 别名 0.8 / 模糊 0.5–0.7。 */
export default function ScoreBadge({ matchType, score, conflicts }: Props) {
  if (!matchType) return <span className="badge">未命中</span>;
  return (
    <span className={`badge badge-${matchType}`}>
      {MATCH_TYPE_LABEL[matchType] ?? matchType}
      {typeof score === 'number' ? ` · ${score.toFixed(2)}` : ''}
      {conflicts ? ` · 冲突 ${conflicts}` : ''}
    </span>
  );
}
