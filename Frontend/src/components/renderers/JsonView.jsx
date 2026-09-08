export default function JsonView({ data }) {
  return <pre className="json">{JSON.stringify(data, null, 2)}</pre>
}
