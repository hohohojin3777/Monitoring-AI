import { useAuthors } from "../lib/data";
import { Chip, platformLabel } from "../lib/ui";

const GRADE_CHIP: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  mid: "bg-orange-100 text-orange-700",
  low: "bg-gray-100 text-gray-600",
};

/** 누적 점수로 영향력 등급 산정 (서버 저장 대신 클라이언트에서 파생) */
function gradeOf(score: number): string {
  return score >= 20 ? "high" : score >= 8 ? "mid" : "low";
}

export default function Authors() {
  const { data, loading } = useAuthors();
  return (
    <div>
      <h1 className="text-xl font-bold text-gray-900">작성자 영향력</h1>
      <p className="mt-0.5 text-sm text-gray-500">
        공개 매체 작성자의 누적 영향력. 개인 추적이 아닌 작성자 단위 집계입니다.
      </p>
      <div className="mt-4 overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-gray-50 text-left text-xs text-gray-500">
            <tr>
              <th className="px-4 py-2.5">등급</th>
              <th className="px-4 py-2.5">작성자</th>
              <th className="px-4 py-2.5">주력 플랫폼</th>
              <th className="px-4 py-2.5 text-right">점수</th>
              <th className="px-4 py-2.5 text-right">글 수</th>
              <th className="px-4 py-2.5 text-right">대상 언급</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-400">
                  불러오는 중…
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-gray-400">
                  아직 영향력 데이터가 없습니다.
                </td>
              </tr>
            ) : (
              data.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-2.5">
                    <Chip className={GRADE_CHIP[gradeOf(a.score)]}>{gradeOf(a.score)}</Chip>
                  </td>
                  <td className="px-4 py-2.5 font-medium">{a.name}</td>
                  <td className="px-4 py-2.5 text-gray-500">{platformLabel(a.mainPlatform)}</td>
                  <td className="px-4 py-2.5 text-right font-semibold">{a.score}</td>
                  <td className="px-4 py-2.5 text-right text-gray-500">{a.postCount}</td>
                  <td className="px-4 py-2.5 text-right text-gray-500">{a.targetMentions}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
