import { useState, useEffect } from "react";
import axios from "axios";
import { TestInfo } from "../types";

const API_URL = import.meta.env.VITE_API_URL || "";

interface TestNavProps {
  currentTest?: string;
  onSelectTest: (testName: string) => void;
}

function TestNav({ currentTest, onSelectTest }: TestNavProps) {
  const [tests, setTests] = useState<TestInfo[]>([]);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    fetchTests();
  }, []);

  const fetchTests = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/tests`);
      setTests(response.data);
    } catch (err) {
      console.error("Failed to fetch tests:", err);
    }
  };

  if (tests.length === 0) return null;

  // Group tests by category
  const testsByCategory = tests.reduce(
    (acc, test) => {
      const cat = test.test_category || "other";
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(test);
      return acc;
    },
    {} as Record<string, TestInfo[]>
  );

  // Sort tests within each category
  Object.values(testsByCategory).forEach((catTests) => {
    catTests.sort((a, b) => a.test_name.localeCompare(b.test_name));
  });

  // Category order
  const categoryOrder = ["cpu", "memory", "disk", "compression", "cryptography", "other"];
  const sortedCategories = Object.keys(testsByCategory).sort((a, b) => {
    const aIdx = categoryOrder.indexOf(a);
    const bIdx = categoryOrder.indexOf(b);
    if (aIdx === -1 && bIdx === -1) return a.localeCompare(b);
    if (aIdx === -1) return 1;
    if (bIdx === -1) return -1;
    return aIdx - bIdx;
  });

  return (
    <div className="test-nav-compact">
      <div className="test-nav-header" onClick={() => setExpanded(!expanded)}>
        <span className="test-nav-label">
          {currentTest ? `Test: ${currentTest}` : "Results by test"}
        </span>
        <span className="test-nav-toggle">{expanded ? "[-]" : "[+]"}</span>
      </div>
      {expanded && (
        <div className="test-nav-dropdown">
          {sortedCategories.map((category) => (
            <div key={category} className="test-nav-cat">
              <span className="test-nav-cat-label">{category}:</span>
              {testsByCategory[category].map((test) => (
                <span
                  key={test.test_name}
                  className={`test-nav-chip ${currentTest === test.test_name ? "active" : ""}`}
                  onClick={() => onSelectTest(test.test_name)}
                >
                  {test.test_name}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default TestNav;
